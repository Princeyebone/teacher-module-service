from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List, Dict, Any, Union
from datetime import date, datetime, time

from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.models.model import (
    TeacherProfile, 
    ClassSession, 
    TeacherPlannerEvent, 
    CalendarEvent, 
    AcademicCalendar
)

router = APIRouter(prefix="/api", tags=["Today's Overview"])

@router.get("/today-overview")
async def get_todays_overview(
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get today's classes and events for the current teacher.
    
    Returns:
    - Classes from ClassSession table
    - Events from TeacherPlannerEvent and CalendarEvent tables
    """
    try:
        today = date.today()
        
        # Get today's class sessions
        class_sessions = (await db.execute(
            select(ClassSession).where(
                ClassSession.teacher_id == current_teacher.id,
                ClassSession.date == today
            )
        )).scalars().all()
        
        # Format class sessions
        classes_data = []
        for session in class_sessions:
            class_item = {
                "id": session.id,
                "title": session.subject,
                "type": "class session",
                "start": session.start_time,
                "end": session.end_time,
                "location": session.location if session.location else None,
                "description": f"Class session for {session.class_name}" if session.class_name else None
            }
            classes_data.append(class_item)
        
        # Get today's events from TeacherPlannerEvent
        planner_events = (await db.execute(
            select(TeacherPlannerEvent).where(
                TeacherPlannerEvent.teacher_id == current_teacher.id,
                TeacherPlannerEvent.date == today
            )
        )).scalars().all()
        
        # Get academic calendar to find related calendar events
        academic_calendar = (await db.execute(
            select(AcademicCalendar).where(AcademicCalendar.teacher_id == current_teacher.id)
        )).scalar_one_or_none()
        
        calendar_events = []
        if academic_calendar:
            # Get calendar events that are happening today
            calendar_events = (await db.execute(
                select(CalendarEvent).where(
                    CalendarEvent.calender_id == academic_calendar.id,
                    CalendarEvent.event_start_date <= today,
                    CalendarEvent.event_end_date >= today
                )
            )).scalars().all()
        
        # Format events
        events_data = []
        
        # Format planner events (personal events)
        for event in planner_events:
            event_item = {
                "id": event.id,
                "title": event.title,
                "type": "personal event",  # from teacher planner table
                "start": event.start_time,
                "end": event.end_time,
                "location": None,  # TeacherPlannerEvent doesn't have location field
                "description": event.description
            }
            events_data.append(event_item)
        
        # Format calendar events (school events)
        for event in calendar_events:
            # Determine event type
            if event.is_holiday:
                event_type = "holiday"
            elif event.requires_no_classes:
                event_type = "no classes"
            else:
                event_type = "school event"  # from calendar event table
                
            # Format time objects to strings
            start_time_str = None
            end_time_str = None
            
            if event.event_start_time:
                if isinstance(event.event_start_time, time):
                    start_time_str = event.event_start_time.isoformat()
                else:
                    start_time_str = str(event.event_start_time)
                    
            if event.event_end_time:
                if isinstance(event.event_end_time, time):
                    end_time_str = event.event_end_time.isoformat()
                else:
                    end_time_str = str(event.event_end_time)
                
            event_item = {
                "id": event.id,
                "title": event.event_name or "Unnamed Event",
                "type": event_type,
                "start": start_time_str,
                "end": end_time_str,
                "location": None,  # CalendarEvent doesn't have location field
                "description": None
            }
            events_data.append(event_item)
        
        # Combine classes and events
        result = classes_data + events_data
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error fetching today's overview: {str(e)}"
        )