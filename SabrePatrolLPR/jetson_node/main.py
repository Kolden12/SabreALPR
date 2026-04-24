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
    alpr_engine_instance = ALPREngineThread()

    # Connect signal to websocket broadcaster
    alpr_engine_instance.new_read_callbacks.append(broadcast_read)

    alpr_engine_instance.start()

    # Start Background Workers (TrueNAS Offload & Webhooks)
    from background_workers import BackgroundWorkers
    from api_webhook import WebhookIntegration

    # We will spin these up using asyncio or threads depending on their structure later

    yield

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
    # settings = {"cam1": {"type": "VSR-20", "ip": "192.168.1.100"}, ...}
    logging.info(f"Received new camera configuration: {settings}")

    if alpr_engine_instance:
        # We need to restart streams
        # Update config logic goes here
        pass

    return {"status": "success"}

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
