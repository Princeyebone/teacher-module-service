from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
import auths_routes
from database import create_all_db_tables
import profile_routes
import teacher_crud
import timetable_crud
import calendar_crud
from fastapi.middleware.cors import CORSMiddleware
from logger import logger
import productivity

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="School ERP - Teacher Module",
        version="1.0.0",
        description="API for Teacher Management and Semester Planning",
        routes=app.routes,
    )
    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer Auth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_all_db_tables()
    print("Database tables initialized")
    yield
    print("Shutting down...")
    # Cleanup temporary files
    try:
        import shutil
        import tempfile
        temp_dir = tempfile.gettempdir()
        # Clean up any temporary timetable files
        print("Cleaning up temporary files...")
    except Exception as e:
        print(f"Cleanup error: {e}")

app = FastAPI(
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)
app.openapi = custom_openapi

# CORS Configuration
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
app.include_router(teacher_crud.router, prefix="/api/teacher", tags=["Teacher Management"])
app.include_router(timetable_crud.router, tags=["Timetable Management"])
app.include_router(calendar_crud.router, tags=["Academic Calendar"])
app.include_router(productivity.router, prefix="/api/teacher")

@app.get("/", tags=["Root"])
async def read_root():
    logger.info("Root endpoint accessed")
    return {"message": "Welcome to the Teacher Module API!"}

