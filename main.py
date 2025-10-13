from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from websocket_manager import connect_student_websocket, disconnect_student_websocket
import json
import asyncio
from monitering import handle_student_log_message
from database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio


# ✅ Local Imports
import auths_routes
import profile_routes
import teacher_crud
import timetable_crud
import calendar_crud
import productivity
from database import create_all_db_tables
from websocket_manager import redis_listener, connect_websocket, disconnect_websocket
from logger import logger
import notifications_crud
import main_calendar_crud
import semester_mapper
import file_handler.tm_file_handler as tm_file_handler
import file_handler.ca_file_handler as ca_file_handler
import file_handler.sem_file_handler as sem_file_handler
import file_handler.curri_file_handler as curri_file_handler
import grade_crud
import gradeweights
import score
import assessment
import student_auth
import publishing
import student_read
import monitering
import answer

# ✅ Custom OpenAPI (Swagger) Docs
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="School ERP - Teacher Module",
        version="1.0.0",
        description="API for Teacher Management and Semester Planning",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer Auth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI with Redis listener...")
    await create_all_db_tables()  # Await the async database initialization
    asyncio.create_task(redis_listener())  # Start Redis Pub/Sub listener
    yield
    print("🛑 Shutting down FastAPI...")


# ✅ Create App (ONLY ONCE)
app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.openapi = custom_openapi

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers with proper tags
app.include_router(auths_routes.router, prefix="/api", tags=["Authentication"])
app.include_router(profile_routes.router, tags=["Profile"])
#app.include_router(teacher_crud.router, prefix="/api/teacher", tags=["Teacher Management"])
app.include_router(timetable_crud.router, tags=["Timetable Management"])
app.include_router(calendar_crud.router, tags=["Academic Calendar"])
app.include_router(productivity.router, prefix="/api/teacher")
app.include_router(notifications_crud.router, prefix="/api/teacher")
app.include_router(main_calendar_crud.router, prefix="/api/teacher")
app.include_router(semester_mapper.router, prefix="/api/teacher")
app.include_router(tm_file_handler.router, prefix="/api/teacher")
app.include_router(ca_file_handler.router, prefix="/api/teacher")
app.include_router(sem_file_handler.router, prefix="/api/teacher")
app.include_router(curri_file_handler.router, prefix="/api/teacher")
app.include_router(grade_crud.router, prefix="/api/teacher")
app.include_router(gradeweights.router, prefix="/api/teacher")
app.include_router(score.router, prefix="/api/teacher")
app.include_router(assessment.router, prefix="/api/teacher")
app.include_router(publishing.router, prefix="/api/teacher")
app.include_router(student_auth.router, prefix="/api/teacher")
app.include_router(student_read.router, prefix="/api/student")
app.include_router(monitering.router, prefix="/api/teacher")
app.include_router(answer.router, prefix="/api/student")

# ✅ WebSocket Endpoint (Only handles live connections)
@app.websocket("/ws/teacher/{teacher_id}")
async def websocket_endpoint(websocket: WebSocket, teacher_id: str):
    await connect_websocket(teacher_id, websocket)
    try:
        while True:
            try:
                # First, try to receive a message with timeout
                data = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                
                # If we get here, we received a message - process it
                if data["type"] == "websocket.receive":
                    # No automatic pong response - frontend handles ping/pong on its side
                    pass
            except asyncio.TimeoutError:
                # No message received within timeout, send ping to test connection
                try:
                    await websocket.send_text("ping")
                    
                    # Now wait for any response with shorter timeout
                    try:
                        await asyncio.wait_for(websocket.receive(), timeout=10.0)
                        # We received some response, connection is alive
                    except asyncio.TimeoutError:
                        break  # Connection is dead
                        
                except Exception:
                    break  # Connection is dead

    except WebSocketDisconnect:
        pass  # Expected when client disconnects
        
    finally:
        # Always attempt to disconnect, the function handles checking if connection exists
        disconnect_websocket(teacher_id, websocket)
        print(f"🔌 WebSocket disconnected for teacher: {teacher_id}")


async def heartbeat(websocket: WebSocket, student_id: str, interval: int = 30):
    """Send ping frames every interval seconds if connection is alive."""
    try:
        while True:
            await asyncio.sleep(interval)
            if websocket.application_state == WebSocketState.CONNECTED:
                # Send a WebSocket ping frame
                await websocket.send_text("ping")
            else:
                print(f"⚠️ Socket already closed for {student_id}")
                break
    except Exception as e:
        print(f"⚠️ Heartbeat error for {student_id}: {e}")

async def process_log_message(log_data: dict):
    """Process log messages in a separate task to avoid blocking the WebSocket loop"""
    try:
        # Get database session
        db_gen = get_db()
        db = await db_gen.__anext__()
        try:
            await handle_student_log_message(log_data, db)
        finally:
            await db_gen.aclose()
    except Exception as e:
        print(f"❌ Error processing log message: {e}")

# ✅ WebSocket Endpoint for Students
@app.websocket("/ws/student/{student_id}")
async def student_websocket_endpoint(websocket: WebSocket, student_id: str):
    await connect_student_websocket(student_id, websocket)
    print(f"🔗 WebSocket connected for student {student_id}")

    # Launch heartbeat
    heartbeat_task = asyncio.create_task(heartbeat(websocket, student_id))

    try:
        while True:
            data = await websocket.receive_text()
            print(f"📥 From {student_id}: {data}")
            # Process student messages here (logs/answers)
            try:
                # Try to parse as JSON
                message_data = json.loads(data)
                # Handle log messages
                if message_data.get("type") == "log":
                    # Process log message in background task
                    asyncio.create_task(process_log_message(message_data))
            except json.JSONDecodeError:
                # Not a JSON message, ignore or handle as needed
                pass
    except WebSocketDisconnect:
        print(f"❌ Student {student_id} disconnected")
    except Exception as e:
        print(f"❌ Error in student WebSocket for {student_id}: {e}")
    finally:
        # Cancel heartbeat task
        if heartbeat_task:
            heartbeat_task.cancel()
        disconnect_student_websocket(student_id, websocket)
        print(f"🔌 WebSocket disconnected for student: {student_id}")

# ✅ Root
@app.get("/", tags=["Root"])
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Teacher Module API!"}