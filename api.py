"""
Layer FastAPI che wrappa OBD_Analyzer e pusha i dati al relay Cloudflare.

"""

import asyncio
import threading
import json
import os
import sys

import uvicorn
import websockets
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from dashboard.data_buffer import DataBuffer
from dashboard.trip_summary import TripSummary
from dashboard.obd_thread import start_reader

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RELAY_URL    = os.getenv("RELAY_URL", "ws://localhost:8787")
RELAY_SECRET = os.getenv("RELAY_SECRET", "")
RELAY_HTTP   = RELAY_URL.replace("wss://", "https://").replace("ws://", "http://")

# ---------------------------------------------------------------------------
# Stato globale
# ---------------------------------------------------------------------------
buffer           = DataBuffer()
trip             = TripSummary()
stop_event       = threading.Event()
current_room     = {"code": None}
relay_task      = None
# ---------------------------------------------------------------------------
# App FastAPI
# ---------------------------------------------------------------------------
app = FastAPI(title="FuelShare Pi API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "mock": config.MOCK_MODE, "room": current_room["code"]}


@app.post("/rooms")
async def create_room():
    global relay_task

    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{RELAY_HTTP}/rooms",
            headers={"X-Relay-Secret": RELAY_SECRET}
        )
        r.raise_for_status()
        data = r.json()

    current_room["code"] = data["code"]
    print(f"[room] Stanza creata: {data['code']}")

    # Cancella il task precedente e avviane uno nuovo
    if relay_task and not relay_task.done():
        relay_task.cancel()
    relay_task = asyncio.create_task(push_to_relay())

    return data


@app.get("/rooms/current")
def current_room_info():
    return current_room


@app.get("/trip/stats")
def trip_stats():
    return trip.get_stats()


@app.get("/trip/latest")
def trip_latest():
    return buffer.latest() or {}


# ---------------------------------------------------------------------------
# Push dati al relay via WebSocket
# ---------------------------------------------------------------------------
async def push_to_relay():
    while True:
        if not current_room["code"]:
            await asyncio.sleep(1)
            continue

        ws_url = f"{RELAY_URL}/rooms/{current_room['code']}?role=pi"
        try:
            async with websockets.connect(ws_url) as ws:
                print(f"[relay] Connesso — stanza {current_room['code']}")
                while True:
                    latest = buffer.latest()
                    if latest:
                        stats = trip.get_stats()
                        payload = {**latest, **stats}
                        await ws.send(json.dumps(payload, default=str))
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"[relay] Disconnesso: {e} — riconnessione in 3s...")
            await asyncio.sleep(3)


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    start_reader(buffer, trip, stop_event)
    print(f"[OBD] Reader avviato — {'MOCK' if config.MOCK_MODE else 'REALE'}")
    print("[relay] In attesa di una stanza...")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)