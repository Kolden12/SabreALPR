import os
import asyncio
import logging
import signal
import sys
import json
import socket
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from jtop import jtop

from db_manager import DBManager

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global references
db = None
connected_clients = set()
camera_heartbeats = {} # {camera_id: last_timestamp}

# Paths
NVME_BASE_DIR = "/mnt/nvme/sabre_data/crops"
UNREAD_DIR = os.path.join(NVME_BASE_DIR, "unread")
PROCESSED_DIR = os.path.join(NVME_BASE_DIR, "processed")

# Ensure directories exist
os.makedirs(UNREAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    logging.info("Starting Jetson Node Services (FastAPI Gateway)...")
    db = DBManager()
    yield
    logging.info("Shutting down Jetson Node Services...")

app = FastAPI(lifespan=lifespan)

# Mount StaticFiles for crops
app.mount("/crops", StaticFiles(directory=NVME_BASE_DIR), name="crops")

# WebSocket for Alerts
@app.websocket("/alerts")
async def alerts_websocket(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logging.info(f"MDT connected to /alerts. Total clients: {len(connected_clients)}")
    try:
        while True:
            await websocket.receive_text() # Keepalive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        logging.info("MDT disconnected from /alerts.")

@app.post("/internal/broadcast")
async def internal_broadcast(payload: dict):
    """Internal endpoint for Watcher service to trigger broadcasts."""
    await broadcast_alert(payload)
    return {"status": "ok"}

async def broadcast_alert(payload: dict):
    msg = json.dumps(payload)
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send_text(msg)
        except Exception as e:
            logging.error(f"WebSocket broadcast error: {e}")
            disconnected.add(client)
    connected_clients.difference_update(disconnected)

# API Endpoints

@app.post("/api/ingest")
async def ingest_crop(camera_id: str, image: UploadFile = File(...)):
    """Cameras POST crops here."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"{ts}_{camera_id}.jpg"
    high_res_path = os.path.join(UNREAD_DIR, filename)

    # In a real scenario, we might create a thumbnail here too
    # For now, we'll use the same for both or placeholder
    thumbnail_path = high_res_path

    with open(high_res_path, "wb") as f:
        f.write(await image.read())

    event_id = db.insert_raw_event(camera_id, high_res_path, thumbnail_path)

    # Update heartbeat
    camera_heartbeats[camera_id] = time.time()

    return {"status": "success", "event_id": event_id}

@app.post("/api/heartbeat")
async def camera_heartbeat(camera_id: str):
    camera_heartbeats[camera_id] = time.time()
    return {"status": "ok"}

@app.get("/api/history")
async def get_history(page: int = 1, limit: int = 50):
    offset = (page - 1) * limit
    history = db.get_history(limit=limit, offset=offset)
    return history

@app.get("/api/status")
async def get_status():
    """Jetson Thermals and Camera Connectivity."""
    stats = {}
    try:
        with jtop() as jetson:
            if jetson.ok():
                stats = {
                    "thermals": jetson.temperature,
                    "cpu": jetson.cpu,
                    "gpu": jetson.gpu,
                    "power": jetson.power,
                    "uptime": jetson.uptime
                }
    except Exception as e:
        logging.error(f"jtop error: {e}")
        stats = {"error": "Could not retrieve jtop stats"}

    # Camera status
    now = time.time()
    cameras = []
    for cam_id, last_ts in camera_heartbeats.items():
        status = "Online" if now - last_ts < 15 else "Offline"
        cameras.append({"camera_id": cam_id, "status": status, "last_seen": last_ts})

    return {
        "jetson": stats,
        "cameras": cameras
    }

@app.post("/api/cmd/ir_kill")
async def ir_kill(camera_id: Optional[str] = None):
    """Sends STROP_OFF UDP broadcast."""
    UDP_IP = "192.168.3.255"
    UDP_PORT = 5005
    MESSAGE = b"STROP_OFF"

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(MESSAGE, (UDP_IP, UDP_PORT))
        logging.info(f"Sent IR Kill broadcast: {MESSAGE}")
        return {"status": "success", "message": "IR Kill command broadcasted"}
    except Exception as e:
        logging.error(f"Failed to send UDP broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/hotlist")
async def update_hotlist(file: UploadFile = File(...)):
    """Upload watchlist and migrate to PostgreSQL."""
    import csv
    import io
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.reader(io.StringIO(decoded))

    conn = db.connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM hot_list")
            for row in reader:
                if row:
                    plate = row[0].strip().upper()
                    desc = row[1] if len(row) > 1 else ""
                    cur.execute("INSERT INTO hot_list (plate_text, description) VALUES (%s, %s) ON CONFLICT DO NOTHING", (plate, desc))
            conn.commit()
    finally:
        db.connection_pool.putconn(conn)

    return {"status": "success"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
