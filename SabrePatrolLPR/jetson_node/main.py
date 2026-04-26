import os
import asyncio
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global references
alpr_engine_instance = None
video_source_color = None
video_source_ir = None

# Connected WebSocket clients (MDTs)
connected_clients = set()

def signal_handler(sig, frame):
    logging.info("Interrupt signal received. Shutting down...")
    # Trigger clean exit
    if alpr_engine_instance:
        alpr_engine_instance.stop()

    # Give it a moment to stop
    time.sleep(1)

    # Close video sources to release hardware resources
    if video_source_color:
        video_source_color.Close()
        globals()['video_source_color'] = None
    if video_source_ir:
        video_source_ir.Close()
        globals()['video_source_ir'] = None

    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global alpr_engine_instance, video_source_color, video_source_ir
    logging.info("Starting Jetson Node Services...")

    # Initialize DB & Tables
    from db_manager import DBManager
    db = DBManager()

    # Start ALPR Engine
    from alpr_engine import ALPREngineThread

    # Jetson-native capture loop using jetson_utils.videoSource
    try:
        import jetson.utils
    except ImportError:
        try:
            from mock_jetson import utils_mod as utils
            import sys
            from types import ModuleType
            if 'jetson' not in sys.modules:
                jetson = ModuleType("jetson")
                sys.modules["jetson"] = jetson
            else:
                jetson = sys.modules["jetson"]
            jetson.utils = utils
            sys.modules["jetson.utils"] = utils
        except ImportError:
            logging.warning("Jetson utils not found and mock_jetson failed to load.")

    import threading
    from config import load_config

    def capture_loop(engine, cam_ip, cam_model):
        global video_source_color, video_source_ir

        if cam_model == "VSR-20":
            url_color = f"rtsp://{cam_ip}:554/stream2"
            url_ir = f"rtsp://{cam_ip}:554/stream1"
        else:
            url_color = f"http://{cam_ip}:8008/camcolor"
            url_ir = f"http://{cam_ip}:8008/camir"

        # Using videoSource for ZeroCopy
        video_source_color = jetson.utils.videoSource(url_color, argv=["--input-codec=h264", "--input-rtsp-transport=tcp"])
        video_source_ir = jetson.utils.videoSource(url_ir, argv=["--input-codec=h264", "--input-rtsp-transport=tcp"])

        logging.info(f"Capture loop started for {cam_model} at {cam_ip}")

        while engine._run_flag:
            try:
                # Capture next frames
                # These are CUDA capsules (ZeroCopy)
                img_color = video_source_color.Capture(timeout=1000)
                img_ir = video_source_ir.Capture(timeout=1000)

                if img_color and img_ir:
                    engine.enqueue_frames(img_color, img_ir)
                else:
                    # Possible timeout or disconnect
                    time.sleep(0.1)
            except Exception as e:
                logging.error(f"Capture error: {e}")
                time.sleep(1.0) # Backoff

    alpr_engine_instance = ALPREngineThread()

    # Connect signal to websocket broadcaster
    alpr_engine_instance.new_read_callbacks.append(broadcast_read)

    alpr_engine_instance.start()

    config = load_config()
    cameras = config.get("cameras", [])
    if cameras:
        cam1 = cameras[0]
        threading.Thread(target=capture_loop, args=(alpr_engine_instance, cam1["ip"], cam1["model"]), daemon=True).start()

    # Start Background Workers
    from background_workers import BackgroundWorkers
    bg_workers = BackgroundWorkers(config)
    bg_workers.start()

    yield

    # Shutdown logic
    logging.info("Shutting down Jetson Node Services...")
    bg_workers.stop()
    if alpr_engine_instance:
        alpr_engine_instance.stop()

    if video_source_color:
        video_source_color.Close()
        video_source_color = None
    if video_source_ir:
        video_source_ir.Close()
        video_source_ir = None

app = FastAPI(lifespan=lifespan)

def broadcast_read(read_data, is_hit):
    """Callback triggered by ALPR engine when a new read occurs. Broadcasts via WebSocket."""
    import base64

    def encode_image(filepath):
        if os.path.exists(filepath):
            try:
                with open(filepath, "rb") as f:
                    return base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass
        return ""

    payload = {
        "type": "new_read",
        "data": read_data,
        "is_hit": is_hit,
        "ir_image_b64": encode_image(read_data.get('ir_path', '')),
        "color_image_b64": encode_image(read_data.get('color_path', ''))
    }

    # Send Webhook
    from api_webhook import WebhookIntegration
    from config import load_config
    config = load_config()
    unit_id = config.get("unit_id", "SABRE-JETSON")
    webhook_url = "https://webhook.site/68467d43-3e4e-423c-981f-4e8a28121249"
    webhook = WebhookIntegration(webhook_url, unit_id, "./archive")
    webhook.send_payload(read_data, is_hit)

    # Create an asyncio task to broadcast
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_ws_message(payload))
    except RuntimeError:
        pass

async def send_ws_message(payload):
    import json
    msg = json.dumps(payload)
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(msg)
        except WebSocketDisconnect:
            disconnected.add(client)
        except Exception as e:
            logging.error(f"WebSocket send error: {e}")
            disconnected.add(client)

    # Clean up dead clients
    connected_clients.difference_update(disconnected)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logging.info(f"New MDT connected. Total clients: {len(connected_clients)}")
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logging.info("MDT disconnected.")

@app.post("/api/settings/cameras")
async def update_cameras(settings: dict):
    """MDT posts camera settings here."""
    from config import load_config, save_config
    logging.info(f"Received new camera configuration: {settings}")

    config = load_config()
    config["cameras"] = settings.get("cameras", [])
    save_config(config)

    # Signal handlers and lifespan will handle clean shutdown on exit
    import sys
    loop = asyncio.get_running_loop()
    loop.call_later(1.0, sys.exit, 0)

    return {"status": "success", "message": "Rebooting Jetson service to apply cameras..."}

@app.post("/api/settings/watchlist")
async def upload_watchlist(file: UploadFile = File(...)):
    """MDT uploads new watchlist.csv"""
    filepath = "watchlist.csv"
    with open(filepath, "wb") as f:
        f.write(await file.read())

    logging.info(f"Updated local watchlist: {file.filename}")
    return {"status": "success", "message": "Watchlist updated successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
