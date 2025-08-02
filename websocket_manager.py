# websocket_manager.py
from fastapi import WebSocket
from typing import Dict, List
import asyncio
import json
import redis.asyncio as aioredis

# Store active WebSocket connections per teacher_id
active_connections: Dict[str, List[WebSocket]] = {}

# Redis configuration
REDIS_URL = "redis://localhost:6379"
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)


async def connect_websocket(teacher_id: str, websocket: WebSocket):
    """Add a new WebSocket connection for a teacher."""
    await websocket.accept()
    if teacher_id not in active_connections:
        active_connections[teacher_id] = []
    active_connections[teacher_id].append(websocket)
    print(f"🔗 WebSocket connected for teacher {teacher_id}")


def disconnect_websocket(teacher_id: str, websocket: WebSocket):
    """Remove a WebSocket connection for a teacher."""
    if teacher_id in active_connections:
        if websocket in active_connections[teacher_id]:
            active_connections[teacher_id].remove(websocket)
        if not active_connections[teacher_id]:
            del active_connections[teacher_id]
    print(f"❌ WebSocket disconnected for teacher {teacher_id}")


async def send_websocket_message(teacher_id: str, message: dict):
    """Send a message to all active WebSocket connections for a teacher."""
    if teacher_id in active_connections:
        disconnected_clients = []
        for ws in active_connections[teacher_id]:
            try:
                await ws.send_json(message)
                print(f"📢 Sent WebSocket message to teacher {teacher_id}: {message}")
            except Exception as e:
                print(f"❌ Error sending WebSocket message to {teacher_id}: {e}")
                disconnected_clients.append(ws)

        # Clean up disconnected clients
        for ws in disconnected_clients:
            active_connections[teacher_id].remove(ws)
        if not active_connections[teacher_id]:
            del active_connections[teacher_id]


async def redis_listener():
    """Listen to Redis Pub/Sub and forward messages to WebSocket clients."""
    pubsub = redis_client.pubsub()
    await pubsub.psubscribe("ws:*")
    print("✅ Redis Pub/Sub listener started...")

    async for message in pubsub.listen():
        if message["type"] == "pmessage":
            channel = message["channel"]
            data = message["data"]

            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON from Redis: {data}")
                continue

            teacher_id = channel.split(":")[1]
            await send_websocket_message(teacher_id, payload)
