"""
Slide API Endpoints

Provides READ and UPDATE endpoints for AI-generated lesson slides.
Slides are generated automatically by the slide_builder scheduler.

Endpoints:
- GET /slides - Get slides for a subject+class (today by default)
- GET /slides/{slide_id} - Get a specific slide deck by ID
- GET /slides/history - Get historical slides (< today)
- PUT /slides/{slide_id} - Update an existing slide deck
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_teacher
from app.models.model import TeacherProfile


router = APIRouter(tags=["Slides"])


# ============================================================================
# SCHEMAS
# ============================================================================

class SlideImage(BaseModel):
    """Image specification within a slide."""
    prompt: Optional[str] = None
    style: Optional[str] = None
    alt: Optional[str] = None


class MCQOption(BaseModel):
    """A single option in a multiple choice question."""
    label: str = ""
    text: str = ""
    
    class Config:
        extra = "allow"


class MultipleChoiceQuestion(BaseModel):
    """A multiple choice question with options and answer."""
    question: str
    options: List[MCQOption] = []
    correct_answer: str
    explanation: Optional[str] = None


class EssayQuestion(BaseModel):
    """An essay question with key points for the answer."""
    question: str
    key_points: List[str] = []
    marks: Optional[int] = None


class SlideContent(BaseModel):
    """Content structure for a single slide."""
    title: Optional[str] = None
    heading: Optional[str] = None
    bullet_points: Optional[List[str]] = None
    questions: Optional[List[str]] = None  # Legacy
    mcq_questions: Optional[List[MultipleChoiceQuestion]] = None
    essay_questions: Optional[List[EssayQuestion]] = None
    image: Optional[SlideImage] = None


class Slide(BaseModel):
    """A single slide in the deck."""
    id: str
    type: str  # title, content, image_content, assessment
    layout: str  # title_center, text_only, image_left_text_right, etc.
    content: SlideContent


class SlideImageStatus(BaseModel):
    """Status of an image associated with a slide."""
    id: UUID
    slide_item_id: str
    prompt: str
    style: Optional[str] = None
    alt_text: Optional[str] = None
    image_url: Optional[str] = None
    status: str  # pending, generating, generated, failed


class SlideDeckResponse(BaseModel):
    """Full slide deck response."""
    id: UUID
    teacher_id: UUID
    subject: str
    class_name: str
    topic: Optional[str] = None
    indicator_ids: List[int] = []
    generation_status: str
    created_at: datetime
    updated_at: datetime
    # The content_json contains the full slide structure
    lesson_id: Optional[str] = None
    class_level: Optional[str] = None
    slides: List[Slide] = []
    # Associated images with generation status
    images: List[SlideImageStatus] = []

    class Config:
        from_attributes = True


class SlideDeckSummary(BaseModel):
    """Summary of a slide deck for history listing."""
    id: UUID
    subject: str
    class_name: str
    topic: Optional[str] = None
    slide_count: int
    created_at: datetime


class SlideHistoryResponse(BaseModel):
    """Response for slide history endpoint."""
    subject: str
    class_name: str
    total_count: int
    slide_decks: List[SlideDeckSummary]


class SlideUpdateRequest(BaseModel):
    """Request schema for updating a slide deck."""
    topic: Optional[str] = None
    content_json: Optional[Dict[str, Any]] = Field(
        None, 
        description="Full slide deck JSON structure (lesson_id, subject, class_level, topic, slides array)"
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def parse_content_json(content_json: dict) -> dict:
    """Parse content_json to extract slide data."""
    slides = []
    for slide_data in content_json.get("slides", []):
        content = slide_data.get("content", {})
        
        # Parse image
        image_data = content.get("image")
        image = None
        if image_data:
            image = SlideImage(
                prompt=image_data.get("prompt"),
                style=image_data.get("style"),
                alt=image_data.get("alt")
            )
        
        # Parse MCQ questions
        mcq_questions = None
        mcq_data = content.get("mcq_questions")
        if mcq_data:
            mcq_questions = []
            for mcq in mcq_data:
                options = []
                for opt in mcq.get("options", []):
                    # Handle various text field names (text, text_content, etc.)
                    text = opt.get("text") or opt.get("text_content") or ""
                    options.append(MCQOption(label=opt.get("label", ""), text=text))
                mcq_questions.append(MultipleChoiceQuestion(
                    question=mcq.get("question", ""),
                    options=options,
                    correct_answer=mcq.get("correct_answer", ""),
                    explanation=mcq.get("explanation")
                ))
        
        # Parse essay questions
        essay_questions = None
        essay_data = content.get("essay_questions")
        if essay_data:
            essay_questions = []
            for essay in essay_data:
                essay_questions.append(EssayQuestion(
                    question=essay.get("question", ""),
                    key_points=essay.get("key_points", []),
                    marks=essay.get("marks")
                ))
        
        slides.append(Slide(
            id=slide_data.get("id", ""),
            type=slide_data.get("type", "content"),
            layout=slide_data.get("layout", "text_only"),
            content=SlideContent(
                title=content.get("title"),
                heading=content.get("heading"),
                bullet_points=content.get("bullet_points"),
                questions=content.get("questions"),
                mcq_questions=mcq_questions,
                essay_questions=essay_questions,
                image=image
            )
        ))
    
    return {
        "lesson_id": content_json.get("lesson_id"),
        "class_level": content_json.get("class_level"),
        "slides": slides
    }


def generate_signed_url(gcs_path: str, expiration_minutes: int = 60) -> Optional[str]:
    """
    Generate a signed URL for a GCS object.
    
    Args:
        gcs_path: The blob path in GCS (e.g., slide_images/{id}/{item}.png)
        expiration_minutes: How long the URL is valid
        
    Returns:
        Signed URL string or None on failure
    """
    try:
        import json
        from datetime import timedelta
        from google.cloud import storage
        from app.core.config import settings
        
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
        print(f"Error generating signed URL: {e}")
        return None



async def get_slide_images(db: AsyncSession, slide_id: UUID) -> List[SlideImageStatus]:
    """Get all images associated with a slide deck with signed URLs.
    
    IMPORTANT: Always generates signed URLs from gcs_path.
    We do NOT use stored image_url as those may be public URLs that cause CORS/ORB errors.
    """
    result = await db.execute(
        text("""
            SELECT id, slide_item_id, prompt, style, alt_text, gcs_path, status
            FROM slide_images
            WHERE slide_id = :slide_id
            ORDER BY slide_item_id
        """),
        {"slide_id": str(slide_id)}
    )
    rows = result.fetchall()
    
    images = []
    for row in rows:
        m = row._mapping
        
        # Always generate signed URL from gcs_path if image is ready
        image_url = None
        gcs_path = m.get("gcs_path")
        
        if m["status"] == "generated" and gcs_path:
            # Generate a fresh signed URL (valid for 60 minutes)
            image_url = generate_signed_url(gcs_path, expiration_minutes=60)
        
        images.append(SlideImageStatus(
            id=m["id"],
            slide_item_id=m["slide_item_id"],
            prompt=m["prompt"],
            style=m.get("style"),
            alt_text=m.get("alt_text"),
            image_url=image_url,
            status=m["status"]
        ))
    return images


# ============================================================================
# READ ENDPOINTS
# ============================================================================

@router.get("/slides", response_model=Optional[SlideDeckResponse])
async def get_slides(
    subject: str = Query(..., description="Subject name"),
    class_name: str = Query(..., description="Class name"),
    slide_date: Optional[date] = Query(None, description="Date to fetch slides for (defaults to today)"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the most recent slide deck for a subject+class on a given date.
    
    If no date is specified, returns slides for today.
    Returns null if no slides exist for the specified date.
    """
    target_date = slide_date or date.today()
    
    result = await db.execute(
        text("""
            SELECT 
                id, teacher_id, subject, class_name, topic,
                indicator_ids, content_json, generation_status,
                created_at, updated_at
            FROM slides
            WHERE teacher_id = :teacher_id
              AND LOWER(subject) = LOWER(:subject)
              AND LOWER(class_name) = LOWER(:class_name)
              AND DATE(created_at) = :target_date
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {
            "teacher_id": str(current_teacher.id),
            "subject": subject,
            "class_name": class_name,
            "target_date": target_date
        }
    )
    row = result.fetchone()
    
    if not row:
        return None
    
    m = row._mapping
    content_json = m["content_json"] or {}
    parsed = parse_content_json(content_json)
    images = await get_slide_images(db, m["id"])
    
    return SlideDeckResponse(
        id=m["id"],
        teacher_id=m["teacher_id"],
        subject=m["subject"],
        class_name=m["class_name"],
        topic=m["topic"],
        indicator_ids=m["indicator_ids"] or [],
        generation_status=m["generation_status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        lesson_id=parsed["lesson_id"],
        class_level=parsed["class_level"],
        slides=parsed["slides"],
        images=images
    )


@router.get("/slides/history", response_model=SlideHistoryResponse)
async def get_slide_history(
    subject: str = Query(..., description="Subject name"),
    class_name: str = Query(..., description="Class name"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get historical slides for a subject+class (slides from before today).
    
    Returns a list of slide deck summaries ordered by date (most recent first).
    """
    today = date.today()
    
    result = await db.execute(
        text("""
            SELECT 
                id, subject, class_name, topic,
                jsonb_array_length(content_json->'slides') as slide_count,
                created_at
            FROM slides
            WHERE teacher_id = :teacher_id
              AND LOWER(subject) = LOWER(:subject)
              AND LOWER(class_name) = LOWER(:class_name)
              AND DATE(created_at) < :today
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {
            "teacher_id": str(current_teacher.id),
            "subject": subject,
            "class_name": class_name,
            "today": today,
            "limit": limit
        }
    )
    rows = result.fetchall()
    
    slide_decks = []
    for row in rows:
        m = row._mapping
        slide_decks.append(SlideDeckSummary(
            id=m["id"],
            subject=m["subject"],
            class_name=m["class_name"],
            topic=m["topic"],
            slide_count=m["slide_count"] or 0,
            created_at=m["created_at"]
        ))
    
    return SlideHistoryResponse(
        subject=subject,
        class_name=class_name,
        total_count=len(slide_decks),
        slide_decks=slide_decks
    )


@router.get("/slides/{slide_id}", response_model=SlideDeckResponse)
async def get_slide_by_id(
    slide_id: UUID = Path(..., description="Slide deck UUID"),
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific slide deck by its ID.
    """
    result = await db.execute(
        text("""
            SELECT 
                id, teacher_id, subject, class_name, topic,
                indicator_ids, content_json, generation_status,
                created_at, updated_at
            FROM slides
            WHERE id = :slide_id
              AND teacher_id = :teacher_id
        """),
        {
            "slide_id": str(slide_id),
            "teacher_id": str(current_teacher.id)
        }
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Slide deck not found")
    
    m = row._mapping
    content_json = m["content_json"] or {}
    parsed = parse_content_json(content_json)
    images = await get_slide_images(db, m["id"])
    
    return SlideDeckResponse(
        id=m["id"],
        teacher_id=m["teacher_id"],
        subject=m["subject"],
        class_name=m["class_name"],
        topic=m["topic"],
        indicator_ids=m["indicator_ids"] or [],
        generation_status=m["generation_status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
        lesson_id=parsed["lesson_id"],
        class_level=parsed["class_level"],
        slides=parsed["slides"],
        images=images
    )


# ============================================================================
# UPDATE ENDPOINT
# ============================================================================

@router.put("/slides/{slide_id}", response_model=SlideDeckResponse)
async def update_slide(
    slide_id: UUID = Path(..., description="Slide deck UUID"),
    update_data: SlideUpdateRequest = None,
    current_teacher: TeacherProfile = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing slide deck.
    
    Allows updating the topic and/or the full content_json.
    This is useful when teachers want to edit AI-generated slides.
    """
    # Verify slide exists and belongs to teacher
    check_result = await db.execute(
        text("""
            SELECT id FROM slides
            WHERE id = :slide_id AND teacher_id = :teacher_id
        """),
        {"slide_id": str(slide_id), "teacher_id": str(current_teacher.id)}
    )
    if not check_result.fetchone():
        raise HTTPException(status_code=404, detail="Slide deck not found")
    
    # Build update query dynamically
    update_fields = []
    params = {"slide_id": str(slide_id)}
    
    if update_data.topic is not None:
        update_fields.append("topic = :topic")
        params["topic"] = update_data.topic
    
    if update_data.content_json is not None:
        update_fields.append("content_json = CAST(:content_json AS jsonb)")
        import json
        params["content_json"] = json.dumps(update_data.content_json)
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="No update data provided")
    
    # Execute update
    update_query = f"""
        UPDATE slides
        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
        WHERE id = :slide_id
    """
    await db.execute(text(update_query), params)
    await db.commit()
    
    # Return updated slide
    return await get_slide_by_id(slide_id, current_teacher, db)
