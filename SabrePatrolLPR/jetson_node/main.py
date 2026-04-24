import os
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global reference to ALPR engine
alpr_engine_instance = None

# Connected WebSocket clients (MDTs)
connected_clients = set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global alpr_engine_instance
    logging.info("Starting Jetson Node Services...")

    # Initialize DB & Tables if needed
    from db_manager import DBManager
    db = DBManager()

    # Start ALPR Engine
    from alpr_engine import ALPREngineThread

    # Simple Video capture loop for Jetson
    import cv2
    import threading
    import time
    from config import load_config

    def capture_loop(engine, cam_ip, cam_model):
        if cam_model == "VSR-20":
            url_color = f"rtsp://{cam_ip}:554/stream2"
            url_ir = f"rtsp://{cam_ip}:554/stream1"
        else:
            url_color = f"http://{cam_ip}:8008/camcolor"
            url_ir = f"http://{cam_ip}:8008/camir"

        cap_c = cv2.VideoCapture(url_color)
        cap_i = cv2.VideoCapture(url_ir)

        while engine._run_flag:
            ret_c, frame_c = cap_c.read()
            ret_i, frame_i = cap_i.read()

            if ret_c and ret_i:
                # Limit queue size to prevent memory leaks if engine falls behind
                if len(engine.frame_queue) < 10:
                    engine.frame_queue.append((frame_c, frame_i))
            else:
                time.sleep(0.1) # Wait on network lag
                # Attempt reconnect logic here in prod

    alpr_engine_instance = ALPREngineThread()

    # Connect signal to websocket broadcaster
    alpr_engine_instance.new_read_callbacks.append(broadcast_read)

    alpr_engine_instance.start()

    config = load_config()
    cameras = config.get("cameras", [])
    if cameras:
        cam1 = cameras[0] # Just primary camera for now as requested
        threading.Thread(target=capture_loop, args=(alpr_engine_instance, cam1["ip"], cam1["model"]), daemon=True).start()

    # Start Background Workers (TrueNAS Offload & Webhooks)
    from background_workers import BackgroundWorkers
    from config import load_config
    config = load_config()

    bg_workers = BackgroundWorkers(config)
    bg_workers.start()

    yield

    bg_workers.stop()

    # Shutdown logic
    logging.info("Shutting down Jetson Node Services...")
    if alpr_engine_instance:
        alpr_engine_instance.stop()

app = FastAPI(lifespan=lifespan)

def broadcast_read(read_data, is_hit):
    """Callback triggered by ALPR engine when a new read occurs. Broadcasts via WebSocket."""
    # Convert image paths to base64 or serve them via static route
    import base64

    def encode_image(filepath):
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
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
        pass # Handle case where loop isn't running in this thread

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
            # We don't expect much from the MDT over WS, just keeping connection alive
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

    # Save the new config locally on the Jetson
    config = load_config()
    config["cameras"] = settings.get("cameras", [])
    save_config(config)

    # NOTE: The simplest robust way to restart the capture threads and ALPR engine with new IP addresses
    # is to let systemd restart the service. We will exit with status 0, and systemd `Restart=always` kicks in.
    import sys
    loop = asyncio.get_running_loop()
    loop.call_later(1.0, sys.exit, 0)

    return {"status": "success", "message": "Rebooting Jetson service to apply cameras..."}

@app.post("/api/settings/watchlist")
async def upload_watchlist(file: UploadFile = File(...)):
    """MDT uploads new watchlist.csv"""
    filepath = "watchlist.csv" # Save to root of jetson_node
    with open(filepath, "wb") as f:
        f.write(await file.read())

    logging.info(f"Updated local watchlist: {file.filename}")
    return {"status": "success", "message": "Watchlist updated successfully"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
