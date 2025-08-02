from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
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


# ✅ Unified Lifespan (DB Init + Redis Listener)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Starting FastAPI with Redis listener...")
    create_all_db_tables()
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
    allow_origins=["http://localhost:5173"],
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

# ✅ WebSocket Endpoint (Only handles live connections)
@app.websocket("/ws/{teacher_id}")
async def websocket_endpoint(websocket: WebSocket, teacher_id: str):
    await connect_websocket(teacher_id, websocket)
    try:
        while True:
            await asyncio.sleep(10)  # Keep alive
    except WebSocketDisconnect:
        disconnect_websocket(teacher_id, websocket)
        print(f"🔌 WebSocket disconnected for teacher: {teacher_id}")


# ✅ Root
@app.get("/", tags=["Root"])
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Teacher Module API!"}