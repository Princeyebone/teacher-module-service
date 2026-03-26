# websocket_manager.py
from fastapi import WebSocket
from typing import Dict, List
import asyncio
import json
import redis.asyncio as aioredis

# Store active WebSocket connections per teacher_id
active_connections: Dict[str, List[WebSocket]] = {}

# Store active WebSocket connections per student_id
student_connections: Dict[str, List[WebSocket]] = {}

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


async def connect_student_websocket(student_id: str, websocket: WebSocket):
    """Add a new WebSocket connection for a student."""
    await websocket.accept()
    if student_id not in student_connections:
        student_connections[student_id] = []
    student_connections[student_id].append(websocket)
    print(f"🔗 WebSocket connected for student {student_id}")


def disconnect_websocket(teacher_id: str, websocket: WebSocket):
    """Remove a WebSocket connection for a teacher."""
    if teacher_id in active_connections:
        if websocket in active_connections[teacher_id]:
            active_connections[teacher_id].remove(websocket)
        if not active_connections[teacher_id]:
            del active_connections[teacher_id]
    print(f"❌ WebSocket disconnected for teacher {teacher_id}")


def disconnect_student_websocket(student_id: str, websocket: WebSocket):
    """Remove a WebSocket connection for a student."""
    if student_id in student_connections:
        if websocket in student_connections[student_id]:
            student_connections[student_id].remove(websocket)
        if not student_connections[student_id]:
            del student_connections[student_id]
    print(f"❌ WebSocket disconnected for student {student_id}")


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


async def send_student_websocket_message(student_id: str, message: dict):
    """Send a message to all active WebSocket connections for a student."""
    if student_id in student_connections:
        disconnected_clients = []
        for ws in student_connections[student_id]:
            try:
                await ws.send_json(message)
                print(f"📢 Sent WebSocket message to student {student_id}: {message}")
            except Exception as e:
                print(f"❌ Error sending WebSocket message to student {student_id}: {e}")
                disconnected_clients.append(ws)

        # Clean up disconnected clients
        for ws in disconnected_clients:
            student_connections[student_id].remove(ws)
        if not student_connections[student_id]:
            del student_connections[student_id]


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

            # Determine if this is for a teacher or student based on channel format
            # e.g., "ws:teacher:teacher_id" or "ws:student:student_id"
            parts = channel.split(":")
            if len(parts) >= 3:
                recipient_type = parts[1]  # "teacher" or "student"
                recipient_id = parts[2]    # teacher_id or student_id
                
                if recipient_type == "teacher":
                    await send_websocket_message(recipient_id, payload)
                elif recipient_type == "student":
                    await send_student_websocket_message(recipient_id, payload)
                    print(f"📢 Forwarded message to student {recipient_id}: {payload}")
            elif len(parts) == 2:
                # Handle the old format "ws:teacher_id" for backward compatibility
                recipient_id = parts[1]
                await send_websocket_message(recipient_id, payload)
                print(f"📢 Forwarded message to teacher {recipient_id}: {payload}")
