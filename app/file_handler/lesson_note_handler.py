"""
Weekly Lesson Notes API Endpoints

Provides READ and UPSERT (Create/Update) endpoints for weekly lesson notes.
Lesson notes are generated automatically but can be edited by teachers.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile

router = APIRouter(tags=["Weekly Lesson Notes"])


# ============================================================================
# SCHEMAS
# ============================================================================

class PhaseContent(BaseModel):
    """Content for a single phase (activity + resources)."""
    activity: str = Field(default="", description="Learner activity description")
    resources: str = Field(default="", description="Teaching/learning resources")


class LessonNoteResponse(BaseModel):
    """
    Response schema for a single lesson note.
    Contains all fields including AI-generated and teacher-editable content.
    """
    id: UUID
    teacher_id: UUID
    subject: str
    class_name: str
    indicator_id: Optional[int] = None
    
    # Header Fields
    week_date: date = Field(description="Friday of the week for this lesson note")
    duration: Optional[str] = Field(None, description="e.g., '12:00 - 13:00'")
    strand: Optional[str] = None
    substrand: Optional[str] = None
    content_standard: Optional[str] = None
    content_standard_code: Optional[str] = None
    indicator_text: Optional[str] = None
    indicator_code: Optional[str] = None
    class_size: Optional[str] = Field(None, description="Teacher fills this manually")
    week_number: Optional[int] = None
    semester_name: Optional[str] = None
    lesson_number: Optional[str] = Field(None, description="e.g., '1 of 3'")
    performance_indicator: Optional[str] = Field(None, description="AI-generated, can be edited")
    core_competency: Optional[str] = Field(None, description="AI-generated, can be edited")
    reference_page: Optional[str] = None
    
    # Phase Contents (3 phases)
    phase1: PhaseContent = Field(description="Phase 1: Starter")
    phase2: PhaseContent = Field(description="Phase 2: New Learning")
    phase3: PhaseContent = Field(description="Phase 3: Reflection")
    
    # Tracking
    generated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class LessonNoteListResponse(BaseModel):
    """
    Response for listing lesson notes for a subject+class.
    Returns a list because there may be multiple indicators (multiple lesson notes).
    """
    subject: str
    class_name: str
    week_date: date
    total_count: int = Field(description="Total number of lesson notes for this subject+class+week")
    lesson_notes: List[LessonNoteResponse]


class LessonNoteUpdateRequest(BaseModel):
    """
    Request schema for updating a lesson note.
    All fields are optional - only provided fields will be updated.
    """
    # Header Fields (teacher can edit these)
    class_size: Optional[str] = Field(None, description="Class size (teacher fills)")
    performance_indicator: Optional[str] = Field(None, description="Edit AI-generated content")
    core_competency: Optional[str] = Field(None, description="Edit AI-generated content")
    
    # Phase Contents (teacher can edit these)
    phase1_activity: Optional[str] = None
    phase1_resources: Optional[str] = None
    phase2_activity: Optional[str] = None
    phase2_resources: Optional[str] = None
    phase3_activity: Optional[str] = None
    phase3_resources: Optional[str] = None


class LessonNoteCreateRequest(BaseModel):
    """
    Request schema for creating/upserting a lesson note manually.
    Used when teacher wants to create a lesson note from scratch.
    """
    subject: str
    class_name: str
    indicator_id: Optional[int] = None
    week_date: date
    
    # Header Fields
    duration: Optional[str] = None
    strand: Optional[str] = None
    substrand: Optional[str] = None
    content_standard: Optional[str] = None
    content_standard_code: Optional[str] = None
    indicator_text: Optional[str] = None
    indicator_code: Optional[str] = None
    class_size: Optional[str] = None
    week_number: Optional[int] = None
    semester_name: Optional[str] = None
    lesson_number: Optional[str] = None
    performance_indicator: Optional[str] = None
    core_competency: Optional[str] = None
    reference_page: Optional[str] = None
    
    # Phase Contents
    phase1_activity: Optional[str] = None
    phase1_resources: Optional[str] = None
    phase2_activity: Optional[str] = None
    phase2_resources: Optional[str] = None
    phase3_activity: Optional[str] = None
    phase3_resources: Optional[str] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def row_to_response(row) -> LessonNoteResponse:
    """Convert a database row to LessonNoteResponse."""
    r = dict(row._mapping)
    return LessonNoteResponse(
        id=r["id"],
        teacher_id=r["teacher_id"],
        subject=r["subject"],
        class_name=r["class_name"],
        indicator_id=r.get("indicator_id"),
        week_date=r["week_date"],
        duration=r.get("duration"),
        strand=r.get("strand"),
        substrand=r.get("substrand"),
        content_standard=r.get("content_standard"),
        content_standard_code=r.get("content_standard_code"),
        indicator_text=r.get("indicator_text"),
        indicator_code=r.get("indicator_code"),
        class_size=r.get("class_size"),
        week_number=r.get("week_number"),
        semester_name=r.get("semester_name"),
        lesson_number=r.get("lesson_number"),
        performance_indicator=r.get("performance_indicator"),
        core_competency=r.get("core_competency"),
        reference_page=r.get("reference_page"),
        phase1=PhaseContent(
            activity=r.get("phase1_activity") or "",
            resources=r.get("phase1_resources") or ""
        ),
        phase2=PhaseContent(
            activity=r.get("phase2_activity") or "",
            resources=r.get("phase2_resources") or ""
        ),
        phase3=PhaseContent(
            activity=r.get("phase3_activity") or "",
            resources=r.get("phase3_resources") or ""
        ),
        generated_at=r.get("generated_at"),
        updated_at=r.get("updated_at")
    )


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/lesson-notes", response_model=LessonNoteListResponse)
async def get_lesson_notes(
    subject: str = Query(..., description="Subject name (e.g., 'Mathematics')"),
    class_name: str = Query(..., description="Class name (e.g., 'Class 8')"),
    week_date: Optional[date] = Query(None, description="Friday date (defaults to current week)"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all lesson notes for a subject+class combination.
    
    Returns a LIST of lesson notes because there may be multiple indicators
    (and thus multiple lesson notes) for a single subject+class in a week.
    
    If week_date is not provided, returns the most recent week's notes.
    """
    # Build query
    if week_date:
        result = await db.execute(
            text("""
                SELECT * FROM weekly_lesson_notes
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND week_date = :week_date
                ORDER BY lesson_number ASC
            """),
            {
                "teacher_id": str(current_teacher.id),
                "subject": subject,
                "class_name": class_name,
                "week_date": week_date
            }
        )
    else:
        # Get most recent week's notes
        result = await db.execute(
            text("""
                SELECT * FROM weekly_lesson_notes
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND class_name = :class_name
                  AND week_date = (
                      SELECT MAX(week_date) FROM weekly_lesson_notes
                      WHERE teacher_id = :teacher_id
                        AND subject = :subject
                        AND class_name = :class_name
                  )
                ORDER BY lesson_number ASC
            """),
            {
                "teacher_id": str(current_teacher.id),
                "subject": subject,
                "class_name": class_name
            }
        )
    
    rows = result.fetchall()
    
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No lesson notes found for {subject} - {class_name}"
        )
    
    # Convert to response objects
    lesson_notes = [row_to_response(row) for row in rows]
    actual_week_date = lesson_notes[0].week_date if lesson_notes else week_date or date.today()
    
    return LessonNoteListResponse(
        subject=subject,
        class_name=class_name,
        week_date=actual_week_date,
        total_count=len(lesson_notes),
        lesson_notes=lesson_notes
    )


@router.get("/lesson-notes/weeks", response_model=List[date])
async def get_available_weeks(
    subject: str = Query(..., description="Subject name"),
    class_name: str = Query(..., description="Class name"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of available week dates for a subject+class.
    Useful for showing a week selector in the frontend.
    """
    result = await db.execute(
        text("""
            SELECT DISTINCT week_date 
            FROM weekly_lesson_notes
            WHERE teacher_id = :teacher_id
              AND subject = :subject
              AND class_name = :class_name
            ORDER BY week_date DESC
        """),
        {
            "teacher_id": str(current_teacher.id),
            "subject": subject,
            "class_name": class_name
        }
    )
    
    weeks = [row[0] for row in result.fetchall()]
    return weeks


@router.get("/lesson-notes/{note_id}", response_model=LessonNoteResponse)
async def get_lesson_note_by_id(
    note_id: UUID = Path(..., description="Lesson note UUID"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific lesson note by its ID.
    """
    result = await db.execute(
        text("""
            SELECT * FROM weekly_lesson_notes
            WHERE id = :note_id
              AND teacher_id = :teacher_id
        """),
        {
            "note_id": str(note_id),
            "teacher_id": str(current_teacher.id)
        }
    )
    
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Lesson note not found")
    
    return row_to_response(row)


# ============================================================================
# UPDATE ENDPOINT
# ============================================================================

@router.put("/lesson-notes/{note_id}", response_model=LessonNoteResponse)
async def update_lesson_note(
    note_id: UUID,
    update_data: LessonNoteUpdateRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a lesson note by ID.
    
    Only the provided fields will be updated.
    This allows teachers to edit AI-generated content.
    """
    # First verify the note exists and belongs to this teacher
    check_result = await db.execute(
        text("""
            SELECT id FROM weekly_lesson_notes
            WHERE id = :note_id AND teacher_id = :teacher_id
        """),
        {"note_id": str(note_id), "teacher_id": str(current_teacher.id)}
    )
    
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Lesson note not found")
    
    # Build dynamic update query
    update_fields = []
    params = {"note_id": str(note_id), "teacher_id": str(current_teacher.id)}
    
    if update_data.class_size is not None:
        update_fields.append("class_size = :class_size")
        params["class_size"] = update_data.class_size
    
    if update_data.performance_indicator is not None:
        update_fields.append("performance_indicator = :performance_indicator")
        params["performance_indicator"] = update_data.performance_indicator
    
    if update_data.core_competency is not None:
        update_fields.append("core_competency = :core_competency")
        params["core_competency"] = update_data.core_competency
    
    if update_data.phase1_activity is not None:
        update_fields.append("phase1_activity = :phase1_activity")
        params["phase1_activity"] = update_data.phase1_activity
    
    if update_data.phase1_resources is not None:
        update_fields.append("phase1_resources = :phase1_resources")
        params["phase1_resources"] = update_data.phase1_resources
    
    if update_data.phase2_activity is not None:
        update_fields.append("phase2_activity = :phase2_activity")
        params["phase2_activity"] = update_data.phase2_activity
    
    if update_data.phase2_resources is not None:
        update_fields.append("phase2_resources = :phase2_resources")
        params["phase2_resources"] = update_data.phase2_resources
    
    if update_data.phase3_activity is not None:
        update_fields.append("phase3_activity = :phase3_activity")
        params["phase3_activity"] = update_data.phase3_activity
    
    if update_data.phase3_resources is not None:
        update_fields.append("phase3_resources = :phase3_resources")
        params["phase3_resources"] = update_data.phase3_resources
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Always update the updated_at timestamp
    update_fields.append("updated_at = :updated_at")
    params["updated_at"] = datetime.utcnow()
    
    # Execute update
    update_query = f"""
        UPDATE weekly_lesson_notes
        SET {', '.join(update_fields)}
        WHERE id = :note_id AND teacher_id = :teacher_id
    """
    
    await db.execute(text(update_query), params)
    await db.commit()
    
    # Return updated record
    return await get_lesson_note_by_id(note_id, current_teacher, db)


# ============================================================================
# CREATE/UPSERT ENDPOINT
# ============================================================================

@router.post("/lesson-notes", response_model=LessonNoteResponse)
async def create_or_update_lesson_note(
    note_data: LessonNoteCreateRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new lesson note or update existing one (UPSERT).
    
    If a lesson note already exists for the same (teacher_id, subject, class_name, 
    indicator_id, week_date) combination, it will be updated.
    """
    # Execute UPSERT
    await db.execute(
        text("""
            INSERT INTO weekly_lesson_notes (
                teacher_id, subject, class_name, indicator_id, week_date,
                duration, strand, substrand, content_standard, content_standard_code,
                indicator_text, indicator_code, class_size, week_number, semester_name,
                lesson_number, performance_indicator, core_competency, reference_page,
                phase1_activity, phase1_resources, phase2_activity, phase2_resources,
                phase3_activity, phase3_resources, generated_at, updated_at
            ) VALUES (
                :teacher_id, :subject, :class_name, :indicator_id, :week_date,
                :duration, :strand, :substrand, :content_standard, :content_standard_code,
                :indicator_text, :indicator_code, :class_size, :week_number, :semester_name,
                :lesson_number, :performance_indicator, :core_competency, :reference_page,
                :phase1_activity, :phase1_resources, :phase2_activity, :phase2_resources,
                :phase3_activity, :phase3_resources, :now, :now
            )
            ON CONFLICT (teacher_id, subject, class_name, indicator_id, week_date)
            DO UPDATE SET
                duration = COALESCE(EXCLUDED.duration, weekly_lesson_notes.duration),
                strand = COALESCE(EXCLUDED.strand, weekly_lesson_notes.strand),
                substrand = COALESCE(EXCLUDED.substrand, weekly_lesson_notes.substrand),
                content_standard = COALESCE(EXCLUDED.content_standard, weekly_lesson_notes.content_standard),
                content_standard_code = COALESCE(EXCLUDED.content_standard_code, weekly_lesson_notes.content_standard_code),
                indicator_text = COALESCE(EXCLUDED.indicator_text, weekly_lesson_notes.indicator_text),
                indicator_code = COALESCE(EXCLUDED.indicator_code, weekly_lesson_notes.indicator_code),
                class_size = COALESCE(EXCLUDED.class_size, weekly_lesson_notes.class_size),
                week_number = COALESCE(EXCLUDED.week_number, weekly_lesson_notes.week_number),
                semester_name = COALESCE(EXCLUDED.semester_name, weekly_lesson_notes.semester_name),
                lesson_number = COALESCE(EXCLUDED.lesson_number, weekly_lesson_notes.lesson_number),
                performance_indicator = COALESCE(EXCLUDED.performance_indicator, weekly_lesson_notes.performance_indicator),
                core_competency = COALESCE(EXCLUDED.core_competency, weekly_lesson_notes.core_competency),
                reference_page = COALESCE(EXCLUDED.reference_page, weekly_lesson_notes.reference_page),
                phase1_activity = COALESCE(EXCLUDED.phase1_activity, weekly_lesson_notes.phase1_activity),
                phase1_resources = COALESCE(EXCLUDED.phase1_resources, weekly_lesson_notes.phase1_resources),
                phase2_activity = COALESCE(EXCLUDED.phase2_activity, weekly_lesson_notes.phase2_activity),
                phase2_resources = COALESCE(EXCLUDED.phase2_resources, weekly_lesson_notes.phase2_resources),
                phase3_activity = COALESCE(EXCLUDED.phase3_activity, weekly_lesson_notes.phase3_activity),
                phase3_resources = COALESCE(EXCLUDED.phase3_resources, weekly_lesson_notes.phase3_resources),
                updated_at = EXCLUDED.updated_at
        """),
        {
            "teacher_id": str(current_teacher.id),
            "subject": note_data.subject,
            "class_name": note_data.class_name,
            "indicator_id": note_data.indicator_id,
            "week_date": note_data.week_date,
            "duration": note_data.duration,
            "strand": note_data.strand,
            "substrand": note_data.substrand,
            "content_standard": note_data.content_standard,
            "content_standard_code": note_data.content_standard_code,
            "indicator_text": note_data.indicator_text,
            "indicator_code": note_data.indicator_code,
            "class_size": note_data.class_size,
            "week_number": note_data.week_number,
            "semester_name": note_data.semester_name,
            "lesson_number": note_data.lesson_number,
            "performance_indicator": note_data.performance_indicator,
            "core_competency": note_data.core_competency,
            "reference_page": note_data.reference_page,
            "phase1_activity": note_data.phase1_activity,
            "phase1_resources": note_data.phase1_resources,
            "phase2_activity": note_data.phase2_activity,
            "phase2_resources": note_data.phase2_resources,
            "phase3_activity": note_data.phase3_activity,
            "phase3_resources": note_data.phase3_resources,
            "now": datetime.utcnow()
        }
    )
    await db.commit()
    
    # Fetch and return the created/updated record
    result = await db.execute(
        text("""
            SELECT * FROM weekly_lesson_notes
            WHERE teacher_id = :teacher_id
              AND subject = :subject
              AND class_name = :class_name
              AND indicator_id = :indicator_id
              AND week_date = :week_date
        """),
        {
            "teacher_id": str(current_teacher.id),
            "subject": note_data.subject,
            "class_name": note_data.class_name,
            "indicator_id": note_data.indicator_id,
            "week_date": note_data.week_date
        }
    )
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create/update lesson note")
    
    return row_to_response(row)
