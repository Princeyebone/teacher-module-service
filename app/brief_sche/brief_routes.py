"""
Lesson Brief API Routes
Read-only endpoints for fetching lesson briefs for the teacher frontend.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile, LessonBrief

router = APIRouter(tags=["Lesson Briefs"])


# --- Response Schemas ---

class LessonBriefResponse(BaseModel):
    """
    Response schema for a single lesson brief.
    The 'brief_content' contains the full markdown-formatted lesson brief.
    """
    id: UUID  # UUID primary key
    teacher_id: UUID
    subject: str
    class_name: str
    session_date: date
    session_id: Optional[int] = None
    previous_session_id: Optional[int] = None
    brief_content: str = Field(description="Full lesson brief in markdown format")
    generated_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class LessonBriefListItem(BaseModel):
    """Compact schema for listing briefs (without full content)."""
    id: UUID  # UUID primary key
    subject: str
    class_name: str
    session_date: date
    generated_at: datetime
    # Preview of the brief (first 200 chars)
    preview: str = Field(description="First 200 characters of the brief")
    
    class Config:
        from_attributes = True


class LessonBriefListResponse(BaseModel):
    """Response for listing multiple briefs."""
    briefs: List[LessonBriefListItem]
    total_count: int


# --- Endpoints ---

@router.get("/lesson-brief/{brief_id}", response_model=LessonBriefResponse)
async def get_lesson_brief_by_id(
    brief_id: UUID,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific lesson brief by ID.
    Returns the full brief content in markdown format.
    """
    result = await db.execute(
        select(LessonBrief).where(
            LessonBrief.id == brief_id,
            LessonBrief.teacher_id == current_teacher.id
        )
    )
    brief = result.scalars().first()
    
    if not brief:
        raise HTTPException(status_code=404, detail="Lesson brief not found")
    
    return LessonBriefResponse(
        id=brief.id,
        teacher_id=brief.teacher_id,
        subject=brief.subject,
        class_name=brief.class_name,
        session_date=brief.session_date,
        session_id=brief.session_id,
        previous_session_id=brief.previous_session_id,
        brief_content=brief.brief_content,
        generated_at=brief.generated_at,
        updated_at=brief.updated_at
    )


@router.get("/lesson-brief", response_model=LessonBriefResponse)
async def get_lesson_brief_by_query(
    subject: str = Query(..., description="Subject name (e.g., 'Mathematics')"),
    class_name: str = Query(..., description="Class name (e.g., 'Class 8')"),
    session_date: Optional[date] = Query(None, description="Session date (optional, for backwards compatibility)"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the lesson brief for a subject and class.
    There is ONE brief per teacher+subject+class that gets updated with each new session.
    
    Returns the full brief content in markdown format.
    """
    # Query by teacher+subject+class only (one brief per combination)
    result = await db.execute(
        select(LessonBrief).where(
            LessonBrief.teacher_id == current_teacher.id,
            LessonBrief.subject == subject,
            LessonBrief.class_name == class_name
        )
    )
    brief = result.scalars().first()
    
    if not brief:
        raise HTTPException(
            status_code=404, 
            detail=f"No lesson brief found for {subject} - {class_name}"
        )
    
    return LessonBriefResponse(
        id=brief.id,
        teacher_id=brief.teacher_id,
        subject=brief.subject,
        class_name=brief.class_name,
        session_date=brief.session_date,
        session_id=brief.session_id,
        previous_session_id=brief.previous_session_id,
        brief_content=brief.brief_content,
        generated_at=brief.generated_at,
        updated_at=brief.updated_at
    )


@router.get("/lesson-briefs", response_model=LessonBriefListResponse)
async def list_lesson_briefs(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    class_name: Optional[str] = Query(None, description="Filter by class"),
    from_date: Optional[date] = Query(None, description="Filter from date"),
    to_date: Optional[date] = Query(None, description="Filter to date"),
    limit: int = Query(20, ge=1, le=100, description="Max number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    List lesson briefs with optional filters.
    Returns compact list items with previews (not full content).
    Use the specific GET endpoint to fetch full content.
    """
    query = select(LessonBrief).where(LessonBrief.teacher_id == current_teacher.id)
    
    if subject:
        query = query.where(LessonBrief.subject == subject)
    if class_name:
        query = query.where(LessonBrief.class_name == class_name)
    if from_date:
        query = query.where(LessonBrief.session_date >= from_date)
    if to_date:
        query = query.where(LessonBrief.session_date <= to_date)
    
    # Get total count
    count_result = await db.execute(query)
    total_count = len(count_result.scalars().all())
    
    # Apply pagination and ordering
    query = query.order_by(desc(LessonBrief.session_date), desc(LessonBrief.generated_at))
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    briefs = result.scalars().all()
    
    brief_items = []
    for brief in briefs:
        # Create preview (first 200 chars)
        preview = brief.brief_content[:200] + "..." if len(brief.brief_content) > 200 else brief.brief_content
        brief_items.append(LessonBriefListItem(
            id=brief.id,
            subject=brief.subject,
            class_name=brief.class_name,
            session_date=brief.session_date,
            generated_at=brief.generated_at,
            preview=preview
        ))
    
    return LessonBriefListResponse(briefs=brief_items, total_count=total_count)


@router.get("/lesson-brief/today/{subject}/{class_name}", response_model=LessonBriefResponse)
async def get_todays_lesson_brief(
    subject: str,
    class_name: str,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the latest lesson brief for a specific subject and class.
    There is ONE brief per teacher+subject+class that always contains the most recent session info.
    """
    result = await db.execute(
        select(LessonBrief).where(
            LessonBrief.teacher_id == current_teacher.id,
            LessonBrief.subject == subject,
            LessonBrief.class_name == class_name
        )
    )
    brief = result.scalars().first()
    
    if not brief:
        raise HTTPException(
            status_code=404, 
            detail=f"No lesson brief found for {subject} - {class_name}"
        )
    
    return LessonBriefResponse(
        id=brief.id,
        teacher_id=brief.teacher_id,
        subject=brief.subject,
        class_name=brief.class_name,
        session_date=brief.session_date,
        session_id=brief.session_id,
        previous_session_id=brief.previous_session_id,
        brief_content=brief.brief_content,
        generated_at=brief.generated_at,
        updated_at=brief.updated_at
    )

