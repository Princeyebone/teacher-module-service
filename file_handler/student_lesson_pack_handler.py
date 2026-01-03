"""
Student Lesson Pack API Endpoints

Provides READ and UPDATE endpoints for AI-generated student lesson packs.
Student packs are generated automatically after teacher slides are created.

Endpoints:
- GET /student-packs - Get student pack for a subject+class (today by default)
- GET /student-packs/{pack_id} - Get a specific student pack by ID
- GET /student-packs/by-session/{session_id} - Get student pack by session ID
- PUT /student-packs/{pack_id} - Update an existing student pack
- GET /student-packs/{pack_id}/audio - Get signed URL for podcast audio
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from uuid import UUID
import json
import logging

from database import get_db
from dependencies import get_current_teacher
from model import TeacherProfile
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Student Lesson Packs"])


# ============================================================================
# SCHEMAS
# ============================================================================

class VideoResource(BaseModel):
    """A video resource with metadata."""
    title: str
    url: str
    thumbnail: Optional[str] = None
    duration: Optional[str] = None
    views: Optional[str] = None
    type: str = "video"  # video or short


class MCQOption(BaseModel):
    """A single option in a multiple choice question."""
    label: str = ""
    text: str = ""
    
    class Config:
        extra = "allow"


class MCQQuestion(BaseModel):
    """A multiple choice question."""
    question: str
    options: List[MCQOption] = []


class MCQAnswer(BaseModel):
    """Answer for an MCQ question."""
    question_number: int
    question: str
    correct_answer: str
    explanation: Optional[str] = None


class EssayQuestion(BaseModel):
    """An essay question."""
    question: str
    marks: Optional[int] = None


class EssayAnswer(BaseModel):
    """Answer key for an essay question."""
    question_number: int
    question: str
    key_points: List[str] = []
    marks: Optional[int] = None


class StudentPackSlideContent(BaseModel):
    """Content for a slide in the student pack."""
    title: Optional[str] = None
    subtitle: Optional[str] = None
    html_content: Optional[str] = None
    description: Optional[str] = None
    videos: Optional[List[VideoResource]] = None
    audio_url: Optional[str] = None
    duration_ms: Optional[int] = None
    instructions: Optional[str] = None
    questions: Optional[List[Any]] = None
    note: Optional[str] = None
    answers: Optional[List[Any]] = None
    
    # Image fields for visual_resource slides (single image)
    image_url: Optional[str] = None  # Signed URL for the image
    gcs_path: Optional[str] = None   # GCS path for the image
    alt_text: Optional[str] = None   # Alt text for accessibility
    caption: Optional[str] = None    # Caption/description for the image
    
    # Images array for visual_gallery slides (multiple images)
    images: Optional[List[Dict[str, Any]]] = None  # List of {gcs_path, image_url, alt_text, caption}
    
    class Config:
        extra = "allow"


class StudentPackSlide(BaseModel):
    """A single slide in the student pack."""
    id: str
    type: str  # title, notes, video_resources, podcast, assessment_mcq, assessment_essay, answer_key_mcq, answer_key_essay
    layout: str
    content: StudentPackSlideContent


class StudentPackSummary(BaseModel):
    """Summary statistics for the student pack."""
    total_slides: int
    has_notes: bool
    image_count: int = 0
    video_count: int
    has_podcast: bool
    podcast_duration_ms: Optional[int] = None
    mcq_count: int
    essay_count: int


class StudentLessonPackResponse(BaseModel):
    """Full student lesson pack response."""
    id: UUID
    teacher_id: UUID
    session_id: int
    slide_id: Optional[UUID] = None
    subject: Optional[str] = None
    class_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    
    # Legacy fields (for backward compatibility)
    simplified_notes: Optional[str] = None
    video_resources: Optional[List[VideoResource]] = None
    podcast_audio_url: Optional[str] = None
    podcast_audio_signed_url: Optional[str] = None  # Signed URL with expiration
    
    # Structured content (new format)
    pack_id: Optional[str] = None
    topic: Optional[str] = None
    generated_at: Optional[str] = None
    slides: List[StudentPackSlide] = []
    summary: Optional[StudentPackSummary] = None

    class Config:
        from_attributes = True


class StudentPackListItem(BaseModel):
    """Summary of a student pack for listing."""
    id: UUID
    session_id: int
    subject: Optional[str] = None
    class_name: Optional[str] = None
    status: str
    has_audio: bool
    video_count: int
    created_at: datetime


class StudentPackUpdateRequest(BaseModel):
    """Request schema for updating a student pack."""
    simplified_notes: Optional[str] = None
    video_resources: Optional[List[Dict[str, Any]]] = None
    content_json: Optional[Dict[str, Any]] = Field(
        None, 
        description="Full structured student pack JSON"
    )


class SignedUrlResponse(BaseModel):
    """Response with signed URL for audio download."""
    original_url: str
    signed_url: str
    expires_in_minutes: int = 60
    content_type: str = "audio/mpeg"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_signed_url(gcs_path: str, expiration_minutes: int = 60) -> Optional[str]:
    """
    Generate a signed URL for a GCS object.
    
    Args:
        gcs_path: The blob path in GCS (e.g., student_packs/{teacher_id}/{session_id}/podcast.mp3)
        expiration_minutes: How long the URL is valid
        
    Returns:
        Signed URL string or None on failure
    """
    try:
        from google.cloud import storage
        
        if not gcs_path:
            return None
        
        # Get GCS credentials
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        # Create storage client
        storage_client = storage.Client.from_service_account_info(service_account_info)
        bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(gcs_path)
        
        # Determine content type based on file extension
        ext = gcs_path.lower().split('.')[-1] if '.' in gcs_path else ''
        content_type_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'webm': 'audio/webm',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'svg': 'image/svg+xml',
            'pdf': 'application/pdf',
        }
        content_type = content_type_map.get(ext, 'application/octet-stream')
        
        # Generate signed URL with proper content type header
        # This prevents ERR_BLOCKED_BY_ORB in browsers
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            response_type=content_type,  # Set Content-Type header in response
        )
        return signed_url
        
    except Exception as e:
        logger.error(f"Error generating signed URL: {e}")
        return None



def extract_gcs_path_from_url(public_url: str) -> Optional[str]:
    """
    Extract the GCS blob path from a public URL.
    
    Example:
        Input: https://storage.googleapis.com/bucket_name/student_packs/id/podcast.mp3
        Output: student_packs/id/podcast.mp3
    """
    if not public_url:
        return None
    
    try:
        # Extract path after bucket name
        prefix = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
        if public_url.startswith(prefix):
            return public_url[len(prefix):]
        return None
    except Exception:
        return None


def parse_student_pack_content(content_json: dict) -> dict:
    """Parse content_json to extract student pack data.
    
    Also converts public GCS URLs to signed URLs for CORS compatibility.
    """
    if not content_json:
        return {"slides": [], "summary": None}
    
    slides = []
    for slide_data in content_json.get("slides", []):
        content = slide_data.get("content", {})
        
        # Convert public GCS URLs to signed URLs for CORS compatibility
        # This prevents ERR_BLOCKED_BY_ORB errors in browsers
        if content.get("audio_url"):
            gcs_path = extract_gcs_path_from_url(content["audio_url"])
            if gcs_path:
                signed_url = generate_signed_url(gcs_path, expiration_minutes=60)
                if signed_url:
                    content["audio_url"] = signed_url
        
        # Convert image GCS paths to signed URLs for visual_resource slides (single image)
        if slide_data.get("type") == "visual_resource" and content.get("gcs_path"):
            signed_url = generate_signed_url(content["gcs_path"], expiration_minutes=60)
            if signed_url:
                content["image_url"] = signed_url
        
        # Convert image GCS paths to signed URLs for visual_gallery slides (multiple images)
        if slide_data.get("type") == "visual_gallery" and content.get("images"):
            for img in content["images"]:
                if img.get("gcs_path"):
                    signed_url = generate_signed_url(img["gcs_path"], expiration_minutes=60)
                    if signed_url:
                        img["image_url"] = signed_url
        
        slides.append(StudentPackSlide(
            id=slide_data.get("id", ""),
            type=slide_data.get("type", "content"),
            layout=slide_data.get("layout", "text_only"),
            content=StudentPackSlideContent(**content)
        ))
    
    summary = None
    if content_json.get("summary"):
        summary = StudentPackSummary(**content_json["summary"])
    
    return {
        "pack_id": content_json.get("pack_id"),
        "topic": content_json.get("topic"),
        "generated_at": content_json.get("generated_at"),
        "slides": slides,
        "summary": summary
    }


def parse_video_resources(video_json: Any) -> List[VideoResource]:
    """Parse video resources from JSON."""
    if not video_json:
        return []
    
    if isinstance(video_json, str):
        try:
            video_json = json.loads(video_json)
        except:
            return []
    
    videos = []
    for v in video_json:
        videos.append(VideoResource(
            title=v.get("title", ""),
            url=v.get("url", ""),
            thumbnail=v.get("thumbnail"),
            duration=v.get("duration"),
            views=v.get("views"),
            type=v.get("type", "video")
        ))
    return videos


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/student-packs", response_model=Optional[StudentLessonPackResponse])
async def get_student_pack(
    subject: str = Query(..., description="Subject name"),
    class_name: str = Query(..., description="Class name"),
    session_id: Optional[int] = Query(None, description="Specific session ID"),
    pack_date: Optional[date] = Query(None, description="Date of the session (not used if session_id provided)"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the student lesson pack for a subject+class.
    
    If session_id is provided, returns that specific session's pack.
    Otherwise, returns the most recent pack for that subject/class combination.
    
    Note: pack_date parameter is kept for backward compatibility but is not currently used
    since packs can be generated at any time for past sessions.
    
    The audio URL is returned with a signed URL valid for 60 minutes.
    """
    
    if session_id:
        # Query by session_id
        query = """
            SELECT 
                id, teacher_id, session_id, slide_id, subject, class_name,
                simplified_notes, video_resources, podcast_audio_url,
                content_json, status, created_at, updated_at
            FROM student_lesson_packs
            WHERE teacher_id = CAST(:teacher_id AS uuid)
              AND session_id = :session_id
            ORDER BY created_at DESC
            LIMIT 1
        """
        params = {
            "teacher_id": str(current_teacher.id),
            "session_id": session_id
        }
    else:
        # Query by subject+class (returns most recent pack)
        query = """
            SELECT 
                id, teacher_id, session_id, slide_id, subject, class_name,
                simplified_notes, video_resources, podcast_audio_url,
                content_json, status, created_at, updated_at
            FROM student_lesson_packs
            WHERE teacher_id = CAST(:teacher_id AS uuid)
              AND LOWER(subject) = LOWER(:subject)
              AND LOWER(class_name) = LOWER(:class_name)
            ORDER BY created_at DESC
            LIMIT 1
        """
        params = {
            "teacher_id": str(current_teacher.id),
            "subject": subject,
            "class_name": class_name
        }
    
    result = await db.execute(text(query), params)
    row = result.fetchone()
    
    if not row:
        return None
    
    m = row._mapping
    
    # Parse content
    content_json = m.get("content_json") or {}
    parsed = parse_student_pack_content(content_json)
    video_resources = parse_video_resources(m.get("video_resources"))
    
    # Generate signed URL for audio
    audio_signed_url = None
    podcast_url = m.get("podcast_audio_url")
    if podcast_url:
        gcs_path = extract_gcs_path_from_url(podcast_url)
        if gcs_path:
            audio_signed_url = generate_signed_url(gcs_path, expiration_minutes=60)
    
    return StudentLessonPackResponse(
        id=m["id"],
        teacher_id=m["teacher_id"],
        session_id=m["session_id"],
        slide_id=m.get("slide_id"),
        subject=m.get("subject"),
        class_name=m.get("class_name"),
        status=m["status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        simplified_notes=m.get("simplified_notes"),
        video_resources=video_resources,
        podcast_audio_url=podcast_url,
        podcast_audio_signed_url=audio_signed_url,
        pack_id=parsed.get("pack_id"),
        topic=parsed.get("topic"),
        generated_at=parsed.get("generated_at"),
        slides=parsed["slides"],
        summary=parsed.get("summary")
    )


@router.get("/student-packs/{pack_id}", response_model=StudentLessonPackResponse)
async def get_student_pack_by_id(
    pack_id: UUID = Path(..., description="Student pack UUID"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific student lesson pack by its ID.
    
    The audio URL is returned with a signed URL valid for 60 minutes.
    """
    result = await db.execute(
        text("""
            SELECT 
                id, teacher_id, session_id, slide_id, subject, class_name,
                simplified_notes, video_resources, podcast_audio_url,
                content_json, status, created_at, updated_at
            FROM student_lesson_packs
            WHERE id = CAST(:pack_id AS uuid)
              AND teacher_id = CAST(:teacher_id AS uuid)
        """),
        {
            "pack_id": str(pack_id),
            "teacher_id": str(current_teacher.id)
        }
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Student pack not found")
    
    m = row._mapping
    
    # Parse content
    content_json = m.get("content_json") or {}
    parsed = parse_student_pack_content(content_json)
    video_resources = parse_video_resources(m.get("video_resources"))
    
    # Generate signed URL for audio
    audio_signed_url = None
    podcast_url = m.get("podcast_audio_url")
    if podcast_url:
        gcs_path = extract_gcs_path_from_url(podcast_url)
        if gcs_path:
            audio_signed_url = generate_signed_url(gcs_path, expiration_minutes=60)
    
    return StudentLessonPackResponse(
        id=m["id"],
        teacher_id=m["teacher_id"],
        session_id=m["session_id"],
        slide_id=m.get("slide_id"),
        subject=m.get("subject"),
        class_name=m.get("class_name"),
        status=m["status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        simplified_notes=m.get("simplified_notes"),
        video_resources=video_resources,
        podcast_audio_url=podcast_url,
        podcast_audio_signed_url=audio_signed_url,
        pack_id=parsed.get("pack_id"),
        topic=parsed.get("topic"),
        generated_at=parsed.get("generated_at"),
        slides=parsed["slides"],
        summary=parsed.get("summary")
    )


@router.get("/student-packs/by-session/{session_id}", response_model=Optional[StudentLessonPackResponse])
async def get_student_pack_by_session(
    session_id: int = Path(..., description="Session ID from timetable"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get student lesson pack by session ID.
    
    This is useful when navigating from timetable to student pack.
    """
    result = await db.execute(
        text("""
            SELECT 
                id, teacher_id, session_id, slide_id, subject, class_name,
                simplified_notes, video_resources, podcast_audio_url,
                content_json, status, created_at, updated_at
            FROM student_lesson_packs
            WHERE teacher_id = CAST(:teacher_id AS uuid)
              AND session_id = :session_id
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {
            "teacher_id": str(current_teacher.id),
            "session_id": session_id
        }
    )
    row = result.fetchone()
    
    if not row:
        return None
    
    m = row._mapping
    
    # Parse content
    content_json = m.get("content_json") or {}
    parsed = parse_student_pack_content(content_json)
    video_resources = parse_video_resources(m.get("video_resources"))
    
    # Generate signed URL for audio
    audio_signed_url = None
    podcast_url = m.get("podcast_audio_url")
    if podcast_url:
        gcs_path = extract_gcs_path_from_url(podcast_url)
        if gcs_path:
            audio_signed_url = generate_signed_url(gcs_path, expiration_minutes=60)
    
    return StudentLessonPackResponse(
        id=m["id"],
        teacher_id=m["teacher_id"],
        session_id=m["session_id"],
        slide_id=m.get("slide_id"),
        subject=m.get("subject"),
        class_name=m.get("class_name"),
        status=m["status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        simplified_notes=m.get("simplified_notes"),
        video_resources=video_resources,
        podcast_audio_url=podcast_url,
        podcast_audio_signed_url=audio_signed_url,
        pack_id=parsed.get("pack_id"),
        topic=parsed.get("topic"),
        generated_at=parsed.get("generated_at"),
        slides=parsed["slides"],
        summary=parsed.get("summary")
    )


@router.get("/student-packs/list", response_model=List[StudentPackListItem])
async def list_student_packs(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    class_name: Optional[str] = Query(None, description="Filter by class"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    List all student packs for the teacher.
    
    Optionally filter by subject and/or class.
    """
    query = """
        SELECT 
            id, session_id, subject, class_name, status,
            podcast_audio_url,
            COALESCE(jsonb_array_length(video_resources::jsonb), 0) as video_count,
            created_at
        FROM student_lesson_packs
        WHERE teacher_id = CAST(:teacher_id AS uuid)
    """
    params = {"teacher_id": str(current_teacher.id), "limit": limit}
    
    if subject:
        query += " AND LOWER(subject) = LOWER(:subject)"
        params["subject"] = subject
    
    if class_name:
        query += " AND LOWER(class_name) = LOWER(:class_name)"
        params["class_name"] = class_name
    
    query += " ORDER BY created_at DESC LIMIT :limit"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    items = []
    for row in rows:
        m = row._mapping
        items.append(StudentPackListItem(
            id=m["id"],
            session_id=m["session_id"],
            subject=m.get("subject"),
            class_name=m.get("class_name"),
            status=m["status"],
            has_audio=bool(m.get("podcast_audio_url")),
            video_count=m.get("video_count", 0),
            created_at=m["created_at"]
        ))
    
    return items


# ============================================================================
# UPDATE ENDPOINT
# ============================================================================

@router.put("/student-packs/{pack_id}", response_model=StudentLessonPackResponse)
async def update_student_pack(
    pack_id: UUID = Path(..., description="Student pack UUID"),
    update_data: StudentPackUpdateRequest = None,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing student lesson pack.
    
    Allows updating:
    - simplified_notes: The HTML notes content
    - video_resources: List of video resources
    - content_json: Full structured pack JSON
    
    This is useful when teachers want to edit AI-generated content.
    """
    # Verify pack exists and belongs to teacher
    check_result = await db.execute(
        text("""
            SELECT id FROM student_lesson_packs
            WHERE id = CAST(:pack_id AS uuid)
              AND teacher_id = CAST(:teacher_id AS uuid)
        """),
        {"pack_id": str(pack_id), "teacher_id": str(current_teacher.id)}
    )
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Student pack not found")
    
    # Build update query dynamically
    update_fields = []
    params = {"pack_id": str(pack_id)}
    
    if update_data.simplified_notes is not None:
        update_fields.append("simplified_notes = :notes")
        params["notes"] = update_data.simplified_notes
    
    if update_data.video_resources is not None:
        update_fields.append("video_resources = CAST(:videos AS jsonb)")
        params["videos"] = json.dumps(update_data.video_resources)
    
    if update_data.content_json is not None:
        update_fields.append("content_json = CAST(:content_json AS jsonb)")
        params["content_json"] = json.dumps(update_data.content_json)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Execute update
    update_query = f"""
        UPDATE student_lesson_packs
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = CAST(:pack_id AS uuid)
    """
    await db.execute(text(update_query), params)
    await db.commit()
    
    # Return updated pack
    return await get_student_pack_by_id(pack_id, current_teacher, db)


# ============================================================================
# AUDIO ENDPOINT (Get Signed URL)
# ============================================================================

@router.get("/student-packs/{pack_id}/audio", response_model=SignedUrlResponse)
async def get_student_pack_audio_url(
    pack_id: UUID = Path(..., description="Student pack UUID"),
    expiration_minutes: int = Query(60, ge=5, le=1440, description="URL expiration in minutes"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a signed URL for the podcast audio file.
    
    The signed URL allows direct download/streaming of the audio file.
    Default expiration is 60 minutes, max is 24 hours (1440 minutes).
    """
    result = await db.execute(
        text("""
            SELECT podcast_audio_url
            FROM student_lesson_packs
            WHERE id = CAST(:pack_id AS uuid)
              AND teacher_id = CAST(:teacher_id AS uuid)
        """),
        {"pack_id": str(pack_id), "teacher_id": str(current_teacher.id)}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Student pack not found")
    
    podcast_url = row._mapping.get("podcast_audio_url")
    if not podcast_url:
        raise HTTPException(status_code=404, detail="No audio available for this pack")
    
    gcs_path = extract_gcs_path_from_url(podcast_url)
    if not gcs_path:
        raise HTTPException(status_code=500, detail="Could not parse audio URL")
    
    signed_url = generate_signed_url(gcs_path, expiration_minutes=expiration_minutes)
    if not signed_url:
        raise HTTPException(status_code=500, detail="Failed to generate signed URL")
    
    return SignedUrlResponse(
        original_url=podcast_url,
        signed_url=signed_url,
        expires_in_minutes=expiration_minutes,
        content_type="audio/mpeg"
    )
