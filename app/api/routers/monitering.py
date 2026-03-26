from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid import UUID
from datetime import datetime
from app.models.model import SurveillanceLog
from app.core.database import get_db
from app.core.logger import logger
from app.sch_ground.background import publish_ws_message
import json

router = APIRouter(tags=["Monitoring"])

def to_naive_datetime(dt: datetime) -> datetime:
    """Convert timezone-aware datetime to naive datetime for database consistency"""
    if dt.tzinfo is not None:
        # Convert to UTC and remove timezone info
        return dt.astimezone().replace(tzinfo=None)
    return dt

async def process_student_log(log_data: dict, db: AsyncSession):
    """Process student log messages and store in SurveillanceLog table, then forward to teacher"""
    try:
        # Extract data from log
        data = log_data.get("data", {})
        log_id = data.get("id")  # Unique identifier for the log
        
        # Check if this log already exists in the database
        if log_id:
            existing_log_query = select(SurveillanceLog).where(SurveillanceLog.id == log_id)
            existing_log_result = await db.execute(existing_log_query)
            existing_log = existing_log_result.scalars().first()
            
            if existing_log:
                logger.info(f"Duplicate log detected with ID: {log_id}, skipping...")
                return existing_log
        
        # Parse datetime fields and convert to naive datetime
        def parse_datetime_field(field_name: str):
            field_value = data.get(field_name)
            if field_value:
                try:
                    if isinstance(field_value, str):
                        dt = datetime.fromisoformat(field_value.replace("Z", "+00:00"))
                        return to_naive_datetime(dt)
                    elif isinstance(field_value, datetime):
                        return to_naive_datetime(field_value)
                except Exception as e:
                    logger.warning(f"Error parsing {field_name}: {e}")
            return datetime.utcnow()
        
        # Create SurveillanceLog entry
        surveillance_log = SurveillanceLog(
            id=log_id,  # Use the provided ID to prevent duplicates
            teacher_id=UUID(data.get("teacher_id")),
            assignment_id=data.get("assignment_id"),
            student_id=data.get("student_id"),
            student_name=data.get("student_name"),
            log_type=data.get("log_type"),
            log_info=data.get("log_info", {}),
            is_began=data.get("is_began", False),
            is_completed=data.get("is_completed", False),
            timestamp=parse_datetime_field("timestamp"),
            time_spent=data.get("time_spent"),
            question_id=data.get("question_id"),
            event_category=data.get("event_category"),
            last_updated=parse_datetime_field("last_updated"),
            created_at=parse_datetime_field("created_at"),
            updated_at=parse_datetime_field("updated_at")
        )
        
        # Add to database
        db.add(surveillance_log)
        await db.commit()
        await db.refresh(surveillance_log)
        
        logger.info(f" SurveillanceLog entry created with ID: {surveillance_log.id}")
        
        # Forward log to teacher via WebSocket
        teacher_id = data.get("teacher_id")
        if teacher_id:
            # Create message for teacher
            teacher_message = {
                "type": "STUDENT_LOG",
                "log_id": surveillance_log.id,
                "data": data
            }
            
            try:
                await publish_ws_message(teacher_id, teacher_message)
                logger.info(f"Log forwarded to teacher {teacher_id}")
            except Exception as e:
                logger.error(f"Failed to forward log to teacher {teacher_id}: {str(e)}")
        
        return surveillance_log
        
    except Exception as e:
        logger.error(f"Error processing student log: {str(e)}")
        await db.rollback()
        raise

# Keep track of recently processed logs to prevent duplicates in memory
_recent_logs = set()
import asyncio

# WebSocket endpoint for receiving student logs would typically be in main.py
# But we can create a helper function here to process logs received via WebSocket

async def handle_student_log_message(websocket_message: dict, db: AsyncSession):
    """Handle incoming WebSocket log messages from students"""
    try:
        # Check if message type is "log"
        if websocket_message.get("type") == "log":
            data = websocket_message.get("data", {})
            log_id = data.get("id")
            
            # Check if we've recently processed this log
            if log_id and log_id in _recent_logs:
                logger.info(f"Duplicate log message detected in memory cache: {log_id}, skipping...")
                return
            
            # Add to recent logs set
            if log_id:
                _recent_logs.add(log_id)
                # Remove from set after 10 seconds to prevent memory bloat
                async def remove_from_cache():
                    await asyncio.sleep(10)
                    _recent_logs.discard(log_id)
                asyncio.create_task(remove_from_cache())
            
            logger.info(f"Processing log message from student: {websocket_message}")
            await process_student_log(websocket_message, db)
        else:
            logger.debug(f"Non-log message received: {websocket_message.get('type')}")
            
    except Exception as e:
        logger.error(f"Error handling student log message: {str(e)}")
        raise