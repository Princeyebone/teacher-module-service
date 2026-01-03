from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from database import get_db
from dependencies import get_current_teacher
from model import TeacherProfile, Outline
from logger import logger

router = APIRouter(tags=["Course Outline"])

# --- Pydantic Schemas ---

class Terminology(BaseModel):
    type: str = "Course"
    role: str = "Lecturer"

class LectureInfo(BaseModel):
    left: List[Dict[str, str]] = []
    right: List[Dict[str, str]] = []

class CourseContentItem(BaseModel):
    week: Optional[int] = None # Not sent to frontend, used internally or optional
    topic: str = ""
    activity: str = ""

class OutlineBase(BaseModel):
    terminology: Terminology = Field(default_factory=Terminology)
    schoolInfoHeaders: List[str] = []
    lectureInfo: LectureInfo = Field(default_factory=LectureInfo)
    courseObjectives: List[str] = [""]
    courseDescription: str = ""
    learningOutcomes: List[str] = [""]
    courseDelivery: str = ""
    courseContent: List[CourseContentItem] = []
    policies: List[str] = [""]
    
    # Metadata
    subjectName: Optional[str] = None
    className: Optional[str] = None
    academicYear: Optional[str] = None
    semester: Optional[str] = None
    
    # Status
    status: str = "draft"
    version: int = 1

class OutlineCreate(OutlineBase):
    pass

class OutlineUpdate(OutlineBase):
    id: Optional[int] = None

class OutlineResponse(OutlineBase):
    id: Optional[int] = None
    teacher_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_auto_save: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- Helper Functions ---

def outline_to_model(outline_data: OutlineBase, teacher_id: UUID) -> Outline:
    """Convert OutlineBase schema to Outline model for database storage."""
    import json
    
    # Ensure course content has weeks 1-indexed if missing
    content_list = []
    for idx, item in enumerate(outline_data.courseContent):
        data = item.model_dump(exclude_none=True)
        if "week" not in data:
            data["week"] = idx + 1
        content_list.append(data)
    
    # Serialize the entire outline data to JSON string for storage
    outline_dict = outline_data.model_dump()
    outline_dict["courseContent"] = content_list  # Use processed content
    outline_content_json = json.dumps(outline_dict)
    
    return Outline(
        teacher_id=teacher_id,
        subject=outline_data.subjectName or "",  # Map subjectName to subject
        class_name=outline_data.className or "",
        outline_content=outline_content_json,
        academic_level=outline_data.academicYear,
        semester_name=outline_data.semester,
        updated_at=datetime.utcnow()
    )

def update_model_from_schema(outline: Outline, data: OutlineBase):
    """Update an existing Outline model from schema data."""
    import json
    
    # Update content with weeks
    content_list = []
    for idx, item in enumerate(data.courseContent):
        item_data = item.model_dump()
        item_data['week'] = idx + 1
        content_list.append(item_data)
    
    # Serialize the entire outline data to JSON string
    outline_dict = data.model_dump()
    outline_dict["courseContent"] = content_list
    outline_content_json = json.dumps(outline_dict)
    
    # Update model fields
    outline.subject = data.subjectName or outline.subject or ""
    outline.class_name = data.className or outline.class_name or ""
    outline.outline_content = outline_content_json
    outline.academic_level = data.academicYear
    outline.semester_name = data.semester
    outline.updated_at = datetime.utcnow()

def model_to_response(outline: Outline) -> OutlineResponse:
    """Convert Outline model to OutlineResponse by parsing the outline_content JSON."""
    import json
    
    # Parse the outline_content JSON
    try:
        data = json.loads(outline.outline_content) if outline.outline_content else {}
    except (json.JSONDecodeError, TypeError):
        data = {}
    
    # Extract fields from parsed data with defaults
    terminology_data = data.get("terminology", {})
    terminology = Terminology(
        type=terminology_data.get("type", "Course"),
        role=terminology_data.get("role", "Lecturer")
    )
    
    headers = data.get("schoolInfoHeaders", ["", "", ""])
    if not headers:
        headers = ["", "", ""]
    
    lecture_info_data = data.get("lectureInfo", {"left": [], "right": []})
    lecture_info = LectureInfo(**lecture_info_data)
    
    objectives = data.get("courseObjectives", [""])
    if not objectives:
        objectives = [""]
    
    outcomes = data.get("learningOutcomes", [""])
    if not outcomes:
        outcomes = [""]
    
    policies = data.get("policies", [""])
    if not policies:
        policies = [""]
    
    # Handle course content
    raw_content = data.get("courseContent", [])
    content_response = []
    
    if not raw_content:
        # If empty, return 12 empty weeks
        for _ in range(12):
            content_response.append(CourseContentItem(topic="", activity=""))
    else:
        for item in raw_content:
            content_response.append(CourseContentItem(
                topic=item.get("topic", ""),
                activity=item.get("activity", "")
            ))
    
    return OutlineResponse(
        id=outline.id,
        teacher_id=outline.teacher_id,
        created_at=outline.created_at,
        updated_at=outline.updated_at,
        last_auto_save=None,  # Not stored in simplified model
        terminology=terminology,
        schoolInfoHeaders=headers,
        lectureInfo=lecture_info,
        courseObjectives=objectives,
        courseDescription=data.get("courseDescription", ""),
        learningOutcomes=outcomes,
        courseDelivery=data.get("courseDelivery", ""),
        courseContent=content_response,
        policies=policies,
        subjectName=outline.subject,  # Map from model field
        className=outline.class_name,
        academicYear=outline.academic_level,  # Map from model field
        semester=outline.semester_name,  # Map from model field
        status=data.get("status", "draft"),
        version=data.get("version", 1)
    )

# --- Endpoints ---

@router.post("/course-outline/save", response_model=OutlineResponse)
async def save_outline(
    outline_data: OutlineUpdate,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Save Course Outline (Upsert).
    """
    try:
        logger.info(f"💾 [SAVE] Endpoint hit - Teacher ID: {current_teacher.id}")
        logger.debug(f"[SAVE] Received data - ID: {outline_data.id}, Subject: {outline_data.subjectName}, Class: {outline_data.className}")
        
        existing_outline = None

        if outline_data.id:
            logger.debug(f"[SAVE] Looking for existing outline by ID: {outline_data.id}")
            query = select(Outline).where(Outline.id == outline_data.id, Outline.teacher_id == current_teacher.id)
            result = await db.execute(query)
            existing_outline = result.scalar_one_or_none()
            
            if not existing_outline:
                logger.warning(f"[SAVE] Outline with ID {outline_data.id} not found")
                raise HTTPException(status_code=404, detail="Outline with provided ID not found")
        else:
            if outline_data.subjectName and outline_data.className and outline_data.academicYear:
                logger.debug(f"[SAVE] Looking for existing outline by context: {outline_data.subjectName}/{outline_data.className}/{outline_data.academicYear}/{outline_data.semester}")
                query = select(Outline).where(
                    Outline.teacher_id == current_teacher.id,
                    Outline.subject_name == outline_data.subjectName,
                    Outline.class_name == outline_data.className,
                    Outline.academic_year == outline_data.academicYear,
                    Outline.semester == outline_data.semester
                )
                result = await db.execute(query)
                existing_outline = result.scalar_one_or_none()

        if existing_outline:
            logger.info(f"🔄 [SAVE] Updating existing outline: {existing_outline.id}")
            update_model_from_schema(existing_outline, outline_data)
            await db.commit()
            await db.refresh(existing_outline)
            logger.info(f"✅ [SAVE] Successfully updated outline {existing_outline.id}")
            return model_to_response(existing_outline)
        else:
            logger.info(f"✨ [SAVE] Creating new outline")
            new_outline = outline_to_model(outline_data, current_teacher.id)
            db.add(new_outline)
            await db.commit()
            await db.refresh(new_outline)
            logger.info(f"✅ [SAVE] Successfully created outline {new_outline.id}")
            return model_to_response(new_outline)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [SAVE] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save outline: {str(e)}")


@router.get("/course-outline/{outline_id}", response_model=OutlineResponse)
async def get_outline_by_id(
    outline_id: UUID,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Get specific outline by ID"""
    query = select(Outline).where(Outline.id == outline_id, Outline.teacher_id == current_teacher.id)
    result = await db.execute(query)
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Outline not found")
        
    return model_to_response(outline)


@router.get("/course-outline", response_model=OutlineResponse)
async def get_outline_by_query(
    subject_name: str = Query(..., description="Subject Name"),
    class_name: str = Query(..., description="Class Name"),
    academic_year: Optional[str] = Query(None, description="Academic Year"),
    semester: Optional[str] = Query(None, description="Semester"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific course outline by filtering params.
    If no outline exists, returns a default empty template structure (id=None)
    instead of 404, so the frontend can start editing immediately.
    """
    
    query = select(Outline).where(
        Outline.teacher_id == current_teacher.id,
        Outline.subject == subject_name,
        Outline.class_name == class_name
    )
    
    if academic_year:
        query = query.where(Outline.academic_level == academic_year)
    if semester:
        query = query.where(Outline.semester_name == semester)
        
    # Order by most recently updated to handle cases where multiple might match (if year/sem not provided)
    query = query.order_by(Outline.updated_at.desc())
    
    result = await db.execute(query)
    outline = result.scalars().first()
    
    if outline:
        return model_to_response(outline)
    else:
        # Return empty template structure as per spec
        return OutlineResponse(
            id=None,
            teacher_id=current_teacher.id,
            created_at=None,
            updated_at=None,
            schoolInfoHeaders=["", "", ""],
            lectureInfo=LectureInfo(left=[], right=[]),
            courseObjectives=[""],
            learningOutcomes=[""],
            policies=[""],
            courseContent=[CourseContentItem(topic="", activity="") for _ in range(12)], # 12 empty weeks
            subjectName=subject_name,
            className=class_name,
            academicYear=academic_year,
            semester=semester
        )


@router.delete("/course-outline/{outline_id}")
async def delete_outline(
    outline_id: UUID,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Delete specific outline by ID"""
    query = select(Outline).where(Outline.id == outline_id, Outline.teacher_id == current_teacher.id)
    result = await db.execute(query)
    outline = result.scalar_one_or_none()
    
    if not outline:
        raise HTTPException(status_code=404, detail="Outline not found")
        
    await db.delete(outline)
    await db.commit()
    logger.info(f"🗑️ Deleted outline {outline_id}")
    return {"success": True, "message": "Outline deleted successfully"}


@router.delete("/course-outlines/teacher")
async def delete_all_teacher_outlines(
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Delete ALL outlines for the current teacher"""
    logger.warning(f"⚠️ Deleting ALL outlines for teacher {current_teacher.id}")
    
    statement = delete(Outline).where(Outline.teacher_id == current_teacher.id)
    result = await db.execute(statement)
    await db.commit()
    
    return {"success": True, "message": f"Deleted {result.rowcount} outlines for teacher {current_teacher.id}"}


@router.get("/course-outlines", response_model=List[OutlineResponse])
async def list_outlines(
    subject_name: Optional[str] = None,
    class_name: Optional[str] = None,
    academic_year: Optional[str] = None,
    semester: Optional[str] = None,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """List outlines for current teacher with optional filters"""
    query = select(Outline).where(Outline.teacher_id == current_teacher.id)
    
    if subject_name:
        query = query.where(Outline.subject == subject_name)
    if class_name:
        query = query.where(Outline.class_name == class_name)
    if academic_year:
        query = query.where(Outline.academic_level == academic_year)
    if semester:
        query = query.where(Outline.semester_name == semester)
        
    query = query.order_by(Outline.updated_at.desc())
    
    result = await db.execute(query)
    outlines = result.scalars().all()
    
    return [model_to_response(out) for out in outlines]
