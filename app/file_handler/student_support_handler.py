"""
Student Support Pack API Endpoints

Provides CRUD endpoints for personalized student support packs.
These packs are tailored to individual students based on their
interests, health considerations, and learning needs.

Endpoints:
- POST /student-support - Create a support pack (pending state)
- GET /student-support - List support packs for a subject/class
- GET /student-support/{pack_id} - Get a specific support pack
- PUT /student-support/{pack_id} - Update text sections of a pack

Background Processing:
The pack generation is handled by a separate worker process.
Run: python student_back/support_pack_worker.py

Updated: 2025-12-31 16:17 - Using ARQ queue, fixed greenlet_spawn error
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import json

from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile
from app.core.logger import logger

router = APIRouter(tags=["Student Support Packs"])


# ============================================================================
# SCHEMAS
# ============================================================================

class StudentSupportCreateRequest(BaseModel):
    """Request to create a new student support pack."""
    student_name: str = Field(..., description="Name of the student")
    subject: str = Field(..., description="Subject for the lesson")
    class_name: str = Field(..., description="Class name (e.g., 'Class 10A')")
    topic: str = Field(..., description="Topic to cover in the lesson")
    interests: List[str] = Field(default=[], description="Student's interests for personalization")
    health_considerations: Optional[str] = Field(None, description="Health issues or other considerations")


class StudentSupportUpdateRequest(BaseModel):
    """Request to update text sections of a support pack."""
    teacher_instructions: Optional[str] = Field(None, description="Updated teacher instructions")
    notes_update: Optional[str] = Field(None, description="Updated notes content (HTML)")


class StudentSupportSlideContent(BaseModel):
    """Content for a slide in the support pack."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    html_content: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[Dict[str, Any]]] = None
    instructions: Optional[str] = None
    questions: Optional[List[Any]] = None
    note: Optional[str] = None
    answers: Optional[List[Any]] = None
    
    class Config:
        extra = "allow"


class StudentSupportSlide(BaseModel):
    """A single slide in the support pack."""
    id: str
    type: str
    layout: str
    content: StudentSupportSlideContent


class StudentSupportSummary(BaseModel):
    """Summary statistics for the support pack."""
    total_slides: int
    has_notes: bool
    image_count: int = 0
    has_teacher_instructions: bool
    mcq_count: int
    essay_count: int


class StudentSupportPackResponse(BaseModel):
    """Full support pack response."""
    id: UUID
    teacher_id: UUID
    student_name: str
    subject: str
    class_name: str
    edu_sys: Optional[str] = None
    edu_lvl: Optional[str] = None
    topic: str
    interests: List[str] = []
    health_considerations: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    teacher_instructions: Optional[str] = None
    
    # Structured content
    pack_id: Optional[str] = None
    generated_at: Optional[str] = None
    slides: List[StudentSupportSlide] = []
    summary: Optional[StudentSupportSummary] = None
    
    class Config:
        from_attributes = True


class StudentSupportListItem(BaseModel):
    """Summary of a support pack for listing."""
    id: UUID
    student_name: str
    subject: str
    class_name: str
    topic: str
    status: str
    created_at: datetime


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_signed_url(gcs_path: str, expiration_minutes: int = 60) -> Optional[str]:
    """Generate a signed URL for a GCS object."""
    try:
        from google.cloud import storage
        from app.core.config import settings
        import json as json_lib
        
        # Get service account credentials
        if settings.GCS_SERVICE_ACCOUNT_JSON.startswith('{'):
            service_account_info = json_lib.loads(settings.GCS_SERVICE_ACCOUNT_JSON)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON, 'r') as f:
                service_account_info = json_lib.load(f)
        
        # Create storage client
        client = storage.Client.from_service_account_info(service_account_info)
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        
        # Determine content type
        content_type = "image/png"
        if gcs_path.endswith(".jpg") or gcs_path.endswith(".jpeg"):
            content_type = "image/jpeg"
        
        # Generate signed URL
        from datetime import timedelta
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            response_type=content_type
        )
        
        return signed_url
        
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        return None


def parse_support_pack_content(content_json: dict) -> dict:
    """Parse content_json and sign image URLs."""
    if not content_json:
        return {"slides": [], "summary": None}
    
    slides = []
    for slide_data in content_json.get("slides", []):
        content = slide_data.get("content", {})
        
        # Sign image URLs for visual_gallery slides
        if slide_data.get("type") == "visual_gallery" and content.get("images"):
            for img in content["images"]:
                if img.get("gcs_path"):
                    signed_url = generate_signed_url(img["gcs_path"], expiration_minutes=60)
                    if signed_url:
                        img["image_url"] = signed_url
        
        slides.append(StudentSupportSlide(
            id=slide_data.get("id", ""),
            type=slide_data.get("type", "content"),
            layout=slide_data.get("layout", "text_only"),
            content=StudentSupportSlideContent(**content)
        ))
    
    summary = None
    if content_json.get("summary"):
        summary = StudentSupportSummary(**content_json["summary"])
    
    return {
        "pack_id": content_json.get("pack_id"),
        "generated_at": content_json.get("generated_at"),
        "slides": slides,
        "summary": summary
    }


# ============================================================================
# CREATE ENDPOINT
# ============================================================================

@router.post("/student-support", response_model=Dict[str, Any])
async def create_student_support_pack(
    request: StudentSupportCreateRequest,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new personalized student support pack.
    
    The pack is created in the database and immediately enqueued for processing.
    A background worker will pick it up from the Redis queue and generate the content.
    
    Run the worker: python student_back/support_pack_worker.py
    """
    logger.info("=" * 80)
    logger.info("CREATE STUDENT SUPPORT PACK - START")
    logger.info(f"Student: {request.student_name}, Subject: {request.subject}, Topic: {request.topic}")
    
    # Cache teacher_id before any DB operations to avoid lazy loading issues
    teacher_id_str = str(current_teacher.id)
    
    try:
        logger.info("Step 1: Querying edu_sys and edu_lvl from weeklytimetable...")
        
        # Query edu_sys and edu_lvl from weeklytimetable
        result = await db.execute(
            text("""
                SELECT edu_sys, edu_lvl
                FROM weeklytimetable
                WHERE teacher_id = :teacher_id
                  AND subject = :subject
                  AND (pupils = :class_name OR pupils ILIKE :class_pattern)
                LIMIT 1
            """),
            {
                "teacher_id": teacher_id_str,
                "subject": request.subject,
                "class_name": request.class_name,
                "class_pattern": f"%{request.class_name}%"
            }
        )
        row = result.fetchone()
        
        edu_sys = row._mapping.get("edu_sys") if row else None
        edu_lvl = row._mapping.get("edu_lvl") if row else None
        
        logger.info(f"✓ Step 1 complete: edu_sys={edu_sys}, edu_lvl={edu_lvl}")
        logger.info("Step 2: Inserting pack into database...")
        
        # Create the pack entry in database with 'pending' status
        insert_result = await db.execute(
            text("""
                INSERT INTO student_support_packs (
                    teacher_id, student_name, subject, class_name,
                    edu_sys, edu_lvl, topic, interests, health_considerations,
                    status, created_at, updated_at
                ) VALUES (
                    :teacher_id, :student_name, :subject, :class_name,
                    :edu_sys, :edu_lvl, :topic, CAST(:interests AS jsonb), :health_considerations,
                    'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
            """),
            {
                "teacher_id": teacher_id_str,
                "student_name": request.student_name,
                "subject": request.subject,
                "class_name": request.class_name,
                "edu_sys": edu_sys,
                "edu_lvl": edu_lvl,
                "topic": request.topic,
                "interests": json.dumps(request.interests),
                "health_considerations": request.health_considerations
            }
        )
        
        logger.info("✓ Step 2 complete: Insert executed")
        logger.info("Step 3: Fetching pack_id from result...")
        
        pack_id = str(insert_result.fetchone()[0])
        
        logger.info(f"✓ Step 3 complete: pack_id={pack_id}")
        logger.info("Step 4: Committing transaction...")
        
        await db.commit()
        
        logger.info(f"✓ Step 4 complete: Transaction committed")
        logger.info(f"Step 5: Enqueuing job to Redis...")
        
        # Enqueue the job to Redis for immediate processing
        from app.student_back.enqueue_support_pack import enqueue_student_support_pack
        
        job = await enqueue_student_support_pack(
            pack_id=pack_id,
            teacher_id=teacher_id_str,  # Use cached value, not current_teacher.id
            student_name=request.student_name,
            subject=request.subject,
            class_name=request.class_name,
            topic=request.topic,
            interests=request.interests,
            health_considerations=request.health_considerations,
            edu_sys=edu_sys,
            edu_lvl=edu_lvl
        )
        
        logger.info(f"✓ Step 5 complete: Job enqueued with ID {job.job_id}")
        logger.info("=" * 80)
        logger.info("CREATE STUDENT SUPPORT PACK - SUCCESS")
        logger.info("=" * 80)
        
        return {
            "message": "Student support pack created and enqueued for generation",
            "pack_id": pack_id,
            "job_id": job.job_id,
            "status": "pending",
            "student_name": request.student_name,
            "topic": request.topic
        }
        
    except Exception as e:
        import traceback
        logger.error("=" * 80)
        logger.error("CREATE STUDENT SUPPORT PACK - ERROR")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("Traceback:")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        
        try:
            await db.rollback()
            logger.info("Database rolled back successfully")
        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
        
        raise HTTPException(status_code=500, detail=f"Failed to create support pack: {str(e)}")


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/student-support", response_model=List[StudentSupportListItem])
async def list_student_support_packs(
    subject: str = Query(..., description="Subject (required)"),
    class_name: str = Query(..., description="Class name (required)"),
    status: Optional[str] = Query(None, description="Filter by status (pending, processing, completed, failed)"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    List all student support packs for a specific subject and class.
    
    Returns all packs created by the current teacher for the given subject and class.
    Use the pack_id from the response to get full details of a specific pack.
    """
    try:
        query = """
            SELECT id, student_name, subject, class_name, topic, status, created_at
            FROM student_support_packs
            WHERE teacher_id = CAST(:teacher_id AS uuid)
              AND subject = :subject
              AND class_name = :class_name
        """
        params = {
            "teacher_id": str(current_teacher.id),
            "subject": subject,
            "class_name": class_name
        }
        
        if status:
            query += " AND status = :status"
            params["status"] = status
        
        query += " ORDER BY created_at DESC LIMIT 50"
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        packs = []
        for row in rows:
            packs.append(StudentSupportListItem(
                id=row._mapping["id"],
                student_name=row._mapping["student_name"],
                subject=row._mapping["subject"],
                class_name=row._mapping["class_name"],
                topic=row._mapping["topic"],
                status=row._mapping["status"],
                created_at=row._mapping["created_at"]
            ))
        
        return packs
        
    except Exception as e:
        logger.error(f"Failed to list support packs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student-support/{pack_id}", response_model=StudentSupportPackResponse)
async def get_student_support_pack(
    pack_id: UUID = Path(..., description="Support pack ID"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific student support pack by ID."""
    try:
        result = await db.execute(
            text("""
                SELECT id, teacher_id, student_name, subject, class_name,
                       edu_sys, edu_lvl, topic, interests, health_considerations,
                       status, created_at, updated_at, teacher_instructions, content_json
                FROM student_support_packs
                WHERE id = CAST(:pack_id AS uuid)
                  AND teacher_id = CAST(:teacher_id AS uuid)
            """),
            {"pack_id": str(pack_id), "teacher_id": str(current_teacher.id)}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Support pack not found")
        
        # Parse content
        content_json = row._mapping.get("content_json") or {}
        parsed_content = parse_support_pack_content(content_json)
        
        # Parse interests
        interests = row._mapping.get("interests") or []
        if isinstance(interests, str):
            interests = json.loads(interests)
        
        return StudentSupportPackResponse(
            id=row._mapping["id"],
            teacher_id=row._mapping["teacher_id"],
            student_name=row._mapping["student_name"],
            subject=row._mapping["subject"],
            class_name=row._mapping["class_name"],
            edu_sys=row._mapping.get("edu_sys"),
            edu_lvl=row._mapping.get("edu_lvl"),
            topic=row._mapping["topic"],
            interests=interests,
            health_considerations=row._mapping.get("health_considerations"),
            status=row._mapping["status"],
            created_at=row._mapping["created_at"],
            updated_at=row._mapping["updated_at"],
            teacher_instructions=row._mapping.get("teacher_instructions"),
            pack_id=parsed_content.get("pack_id"),
            generated_at=parsed_content.get("generated_at"),
            slides=parsed_content.get("slides", []),
            summary=parsed_content.get("summary")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get support pack: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UPDATE ENDPOINT
# ============================================================================

@router.put("/student-support/{pack_id}", response_model=Dict[str, Any])
async def update_student_support_pack(
    pack_id: UUID = Path(..., description="Support pack ID"),
    request: StudentSupportUpdateRequest = None,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Update text sections of a student support pack.
    
    This allows updating:
    - Teacher instructions
    - Notes content
    """
    try:
        # Verify pack exists and belongs to teacher
        result = await db.execute(
            text("""
                SELECT id, content_json 
                FROM student_support_packs
                WHERE id = CAST(:pack_id AS uuid)
                  AND teacher_id = CAST(:teacher_id AS uuid)
            """),
            {"pack_id": str(pack_id), "teacher_id": str(current_teacher.id)}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Support pack not found")
        
        updates = []
        params = {"pack_id": str(pack_id)}
        
        # Update teacher instructions
        if request.teacher_instructions is not None:
            updates.append("teacher_instructions = :instructions")
            params["instructions"] = request.teacher_instructions
        
        # Update notes in content_json
        if request.notes_update is not None:
            content_json = row._mapping.get("content_json") or {}
            
            # Find and update the notes slide
            for slide in content_json.get("slides", []):
                if slide.get("type") == "notes":
                    slide["content"]["html_content"] = request.notes_update
                    break
            
            updates.append("content_json = CAST(:content AS jsonb)")
            params["content"] = json.dumps(content_json)
        
        if not updates:
            return {"message": "No updates provided", "pack_id": str(pack_id)}
        
        # Execute update
        update_query = f"""
            UPDATE student_support_packs
            SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
            WHERE id = CAST(:pack_id AS uuid)
        """
        await db.execute(text(update_query), params)
        await db.commit()
        
        logger.info(f"Updated support pack {pack_id}")
        
        return {
            "message": "Support pack updated successfully",
            "pack_id": str(pack_id),
            "updated_fields": list(params.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update support pack: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
