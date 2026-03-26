"""
Student Lesson Pack Generator

Generates student-facing content including:
1. Simplified "10-year-old" style notes
2. Curated video resources (YouTube)
3. Podcast-style audio recap (TTS)
"""

import logging
import json
import asyncio
import re
import aiohttp
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from uuid import UUID
from concurrent.futures import ThreadPoolExecutor

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from sqlalchemy import text
from app.core.database import get_db
from app.core.config import settings

# Setup logging
logger = logging.getLogger(__name__)

# ============================================================================
# TTS Client Initialization (Cloud Text-to-Speech API with Gemini TTS)
# ============================================================================
TTS_CLIENT = None
TTS_CREDENTIALS = None
TTS_AVAILABLE = False

def _refresh_tts_client():
    """Refresh TTS client with new credentials if token expired."""
    global TTS_CLIENT, TTS_CREDENTIALS, TTS_AVAILABLE
    
    try:
        from google.cloud import texttospeech
        
        logger.info("[TTS] Refreshing credentials...")
        
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
            TTS_CREDENTIALS = service_account.Credentials.from_service_account_info(credentials_info)
        else:
            TTS_CREDENTIALS = service_account.Credentials.from_service_account_file(
                settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
            )
        
        TTS_CLIENT = texttospeech.TextToSpeechClient(credentials=TTS_CREDENTIALS)
        TTS_AVAILABLE = True
        logger.info("[TTS] Credentials refreshed successfully")
        return True
    except Exception as e:
        logger.error(f"[TTS] Failed to refresh credentials: {e}")
        return False

try:
    from google.cloud import texttospeech
    
    # Initialize TTS client with service account credentials
    logger.info("[INIT] Initializing Cloud Text-to-Speech client...")
    
    if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
        credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        TTS_CREDENTIALS = service_account.Credentials.from_service_account_info(credentials_info)
    else:
        TTS_CREDENTIALS = service_account.Credentials.from_service_account_file(
            settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
        )
    
    # Create the TTS client with credentials
    TTS_CLIENT = texttospeech.TextToSpeechClient(credentials=TTS_CREDENTIALS)
    TTS_AVAILABLE = True
    logger.info("[SUCCESS] Cloud Text-to-Speech client initialized successfully")
    
except ImportError as e:
    logger.warning(f"[WARN] Google TTS library not found: {e}. Audio generation disabled.")
    TTS_AVAILABLE = False
except Exception as e:
    logger.error(f"[ERROR] Failed to initialize TTS client: {e}")
    TTS_AVAILABLE = False


# YouTube search (optional)
try:
    from youtubesearchpython import VideosSearch
    VIDEO_SEARCH_AVAILABLE = True
except ImportError:
    logger.warning("[WARN] youtubesearchpython not found. Video curation disabled.")
    VIDEO_SEARCH_AVAILABLE = False

# Executor for sync tasks (YouTube search, formatting)
executor = ThreadPoolExecutor(max_workers=3)

import time

# ============================================================================
# Retry Helper (similar to embeddings implementation)
# ============================================================================

async def _retry_async(
    func,
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    operation_name: str = "operation"
):
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry (should be a coroutine factory, i.e., lambda: actual_call())
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        operation_name: Name for logging
        
    Returns:
        Result of the function, or None if all retries failed
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            result = await func()
            if attempt > 0:
                logger.info(f"[RETRY] {operation_name} succeeded on attempt {attempt + 1}")
            return result
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            
            # Check for rate limiting or quota errors
            if any(kw in error_str for kw in ["429", "quota", "rate limit", "resource_exhausted"]):
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"[RETRY] {operation_name} rate limited (attempt {attempt + 1}/{max_retries}). Waiting {delay}s...")
                await asyncio.sleep(delay)
                continue
            
            # Check for transient errors
            if any(kw in error_str for kw in ["timeout", "connection", "503", "502", "500"]):
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(f"[RETRY] {operation_name} transient error (attempt {attempt + 1}/{max_retries}): {e}. Waiting {delay}s...")
                await asyncio.sleep(delay)
                continue
            
            # Non-retryable error
            logger.error(f"[ERROR] {operation_name} failed with non-retryable error: {e}")
            raise
    
    logger.error(f"[ERROR] {operation_name} failed after {max_retries} attempts. Last error: {last_error}")
    return None



async def generate_student_pack(
    slide_id: str,
    session_id: str,
    teacher_id: str,
    subject: str,
    class_name: str
) -> bool:
    """
    Main entry point to generate a student lesson pack.
    
    Generates a structured slide-format pack containing:
    1. Notes slides (page by page simplified content)
    2. Video resource slides (with thumbnails)
    3. Podcast audio slide
    4. Assessment slides (MCQ and Essay - questions only)
    5. Answer key slides (at the end)
    """
    logger.info(f"[START] Student Pack Generation for Slide {slide_id}")
    
    try:
        # 1. Fetch full slide JSON (including assessments)
        slide_data = await _fetch_full_slide_data(slide_id)
        if not slide_data:
            logger.error(f"[ERROR] Could not fetch slide data for {slide_id}")
            return False
        
        slides_content = slide_data.get("text_content", "")
        original_slides = slide_data.get("slides", [])
        
        # Initialize DB entry with retry
        pack_id = await _retry_async(
            lambda: _create_initial_pack_entry(teacher_id, session_id, slide_id, subject, class_name),
            max_retries=3,
            operation_name="create_pack_entry"
        )
        if not pack_id:
            return False
        
        # Fetch additional context for AI
        teacher_country = await _get_teacher_country(teacher_id)
        indicator_text = await _get_session_indicator(session_id, teacher_id)
        education_system = await _get_education_system(teacher_id, subject, class_name)
        education_level = await _get_education_level(teacher_id, subject, class_name)
        
        logger.info(f"[CONTEXT] Country: {teacher_country}, Edu System: {education_system}")
        logger.info(f"[CONTEXT] Education Level: {education_level}")
        logger.info(f"[CONTEXT] Indicator: {indicator_text[:100] if indicator_text else 'None'}...")
            
        # 2. Generate simplified notes AND video URLs in ONE AI call
        logger.info("[INFO] Generating notes and videos with AI (single call)...")
        notes_and_videos = await _retry_async(
            lambda: _generate_notes_and_videos(
                slides_content=slides_content,
                original_slides=original_slides,
                subject=subject,
                class_name=class_name,
                indicator=indicator_text,
                education_level=education_level,
                education_system=education_system,
                country=teacher_country
            ),
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0,
            operation_name="AI_notes_and_videos"
        )
        
        notes_html = notes_and_videos.get("notes_html", "")
        videos = notes_and_videos.get("videos", [])  # Direct video URLs from AI
        
        logger.info(f"[INFO] Got {len(videos)} videos from AI")
        
        # 3. Generate Podcast Audio (10 minutes, requires notes)
        audio_url = None
        audio_duration = None
        if notes_html:
            script = await _generate_podcast_script(notes_html)
            if script:
                audio_url, audio_duration = await _synthesize_podcast_audio_with_duration(
                    script, pack_id, teacher_id, session_id
                )
        
        # 4. Extract assessments from original teacher slides
        mcq_questions, essay_questions = _extract_assessments(original_slides)
        
        # 4b. Fetch generated images from teacher's slides
        slide_images = await _fetch_slide_images(slide_id)
        
        # 5. Build structured student pack (slide format)
        student_pack_json = _build_student_pack_slides(
            subject=subject,
            class_name=class_name,
            topic=slide_data.get("topic", subject),
            notes_html=notes_html,
            videos=videos,
            audio_url=audio_url,
            audio_duration=audio_duration,
            mcq_questions=mcq_questions,
            essay_questions=essay_questions,
            slide_images=slide_images
        )
        
        # 6. Update DB with results (with retry)
        await _retry_async(
            lambda: _update_pack_entry_with_json(
                pack_id, notes_html, videos, audio_url, student_pack_json, "completed"
            ),
            max_retries=3,
            operation_name="update_pack_entry"
        )
        
        logger.info(f"[SUCCESS] Student Pack Generation Complete: {pack_id}")
        logger.info(f"[SUMMARY] Notes: {len(notes_html) if notes_html else 0} chars, Videos: {len(videos)}, Audio: {audio_duration}ms, MCQs: {len(mcq_questions)}, Essays: {len(essay_questions)}")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Student Pack Generation Failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def _fetch_full_slide_data(slide_id: str) -> Optional[Dict]:
    """Fetch full slide data including assessments."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("SELECT content_json, topic, subject, class_name FROM slides WHERE id = CAST(:id AS uuid)"),
            {"id": slide_id}
        )
        row = result.fetchone()
        if not row:
            return None
            
        content_json = row._mapping.get("content_json", {})
        slides = content_json.get("slides", [])
        
        # Combine slides into text for notes generation
        text_content = ""
        for slide in slides:
            content = slide.get("content", {})
            title = content.get("title", "") or content.get("heading", "")
            bullets = content.get("bullet_points", [])
            if title:
                text_content += f"\n## {title}\n"
            if bullets:
                text_content += "\n".join([f"- {b}" for b in bullets]) + "\n"
        
        return {
            "slides": slides,
            "text_content": text_content,
            "topic": content_json.get("topic", row._mapping.get("topic", "")),
            "subject": row._mapping.get("subject", ""),
            "class_name": row._mapping.get("class_name", "")
        }
    finally:
        await db_gen.aclose()


async def _fetch_slide_images(slide_id: str) -> List[Dict]:
    """Fetch generated images for a slide from the slide_images table."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("""
                SELECT slide_item_id, gcs_path, alt_text, prompt
                FROM slide_images
                WHERE slide_id = CAST(:slide_id AS uuid)
                  AND status = 'generated'
                  AND gcs_path IS NOT NULL
                ORDER BY slide_item_id
            """),
            {"slide_id": slide_id}
        )
        rows = result.fetchall()
        
        images = []
        for row in rows:
            images.append({
                "slide_item_id": row._mapping.get("slide_item_id"),
                "gcs_path": row._mapping.get("gcs_path"),
                "alt_text": row._mapping.get("alt_text", ""),
                "prompt": row._mapping.get("prompt", "")
            })
        
        logger.info(f"[IMAGES] Found {len(images)} generated images for slide {slide_id}")
        return images
    except Exception as e:
        logger.error(f"[IMAGES] Error fetching images: {e}")
        return []
    finally:
        await db_gen.aclose()


def _extract_assessments(slides: List[Dict]) -> tuple:
    """Extract MCQ and Essay questions from teacher slides."""
    mcq_questions = []
    essay_questions = []
    
    for slide in slides:
        slide_type = slide.get("type", "")
        content = slide.get("content", {})
        
        if slide_type == "assessment_mcq":
            mcq_questions.extend(content.get("mcq_questions", []))
        elif slide_type == "assessment_essay":
            essay_questions.extend(content.get("essay_questions", []))
    
    logger.info(f"[EXTRACT] Found {len(mcq_questions)} MCQs and {len(essay_questions)} essay questions")
    return mcq_questions, essay_questions


def _parse_html_to_slides(html_content: str, start_slide_num: int) -> List[Dict]:
    """
    Parse HTML content into structured slides with smart pagination.
    
    This converts the HTML notes into structured slides, ensuring no single slide
    is overloaded with content. It splits long sections into multiple parts.
    
    Args:
        html_content: HTML string from AI-generated notes
        start_slide_num: Starting slide number for IDs
    
    Returns:
        List of slide dictionaries
    """
    from bs4 import BeautifulSoup
    import re
    import copy
    
    slides = []
    slide_num = start_slide_num
    
    # Constants for pagination limits
    MAX_PARAGRAPHS_PER_SLIDE = 2
    MAX_BULLETS_PER_SLIDE = 5
    MAX_SUBSECTIONS_PER_SLIDE = 1
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all h2 sections (main sections)
        h2_elements = soup.find_all('h2')
        
        if not h2_elements:
            # No h2 found, verify length and potentially split by h3 or paragraphs
            # For now, simplistic fallback to h3 if no h2
            h3_elements = soup.find_all('h3')
            if h3_elements:
                # Treat h3 as h2 equivalent in fallback mode
                # Recursive call with h3 replaced by h2 could function, but let's just use existing logic
                # by renaming tags in soup
                for h3 in h3_elements:
                    h3.name = 'h2'
                h2_elements = soup.find_all('h2')
            else:
                # Fallback to single slide
                slides.append({
                    "id": f"slide-{slide_num}",
                    "type": "notes_section",
                    "layout": "text_only",
                    "content": {
                        "title": "Simplified Lesson Notes",
                        "html_content": html_content,
                        "sections": [{"heading": "Lesson Notes", "body": html_content}]
                    }
                })
                return slides
        
        # Process each h2 section
        for h2 in h2_elements:
            section_title = h2.get_text(strip=True)
            
            # Content accumulation buckets
            current_slide_content = {
                "title": section_title,
                "content_parts": [],
                "paragraphs": [],
                "bullet_points": [],
                "subsections": []
            }
            
            paragraph_count = 0
            bullet_count = 0
            
            def commit_current_slide(part_num=None):
                nonlocal slide_num, current_slide_content, paragraph_count, bullet_count
                
                # Don't create empty slides
                if not current_slide_content["content_parts"] and not current_slide_content["subsections"]:
                    return

                # Determine layout
                layout = "text_only"
                if current_slide_content["subsections"]:
                    layout = "content_with_subsections"
                elif current_slide_content["bullet_points"] and current_slide_content["paragraphs"]:
                    layout = "content_with_bullets"
                elif current_slide_content["bullet_points"]:
                    layout = "bullet_list"
                
                # Final content object construction
                slide_content_obj = {
                    "title": f"{section_title} (Part {part_num})" if part_num and part_num > 1 else section_title,
                    "content_parts": copy.deepcopy(current_slide_content["content_parts"])
                }
                
                if current_slide_content["paragraphs"]:
                    # Combine first few paragraphs for the 'body' field summary
                    slide_content_obj["body"] = " ".join(current_slide_content["paragraphs"])
                
                if current_slide_content["bullet_points"]:
                    slide_content_obj["bullet_points"] = copy.deepcopy(current_slide_content["bullet_points"])
                    
                if current_slide_content["subsections"]:
                    slide_content_obj["subsections"] = copy.deepcopy(current_slide_content["subsections"])

                slides.append({
                    "id": f"slide-{slide_num}",
                    "type": "notes_section",
                    "layout": layout,
                    "content": slide_content_obj
                })
                slide_num += 1
                
                # Reset accumulators
                current_slide_content["content_parts"] = []
                current_slide_content["paragraphs"] = []
                current_slide_content["bullet_points"] = []
                current_slide_content["subsections"] = []
                paragraph_count = 0
                bullet_count = 0

            part_counter = 1
            
            # Iterate siblings until next h2
            current = h2.find_next_sibling()
            while current and current.name != 'h2':
                should_break_slide = False
                
                if current.name == 'h3':
                    # Subsections are "heavy" content, usually warrant a check or a dedicated slide
                    # if we already have content, commit it first
                    if paragraph_count > 0 or bullet_count > 0:
                        commit_current_slide(part_counter)
                        part_counter += 1
                    
                    subsection_title = current.get_text(strip=True)
                    subsection_content_parts = []
                    
                    # Gather subsection children
                    sub_current = current.find_next_sibling()
                    while sub_current and sub_current.name not in ['h2', 'h3']:
                        if sub_current.name == 'p':
                             subsection_content_parts.append({
                                "type": "paragraph",
                                "text": sub_current.get_text(strip=True)
                            })
                        elif sub_current.name in ['ul', 'ol']:
                            items = [li.get_text(strip=True) for li in sub_current.find_all('li')]
                            tag_type = "bullet_list" if sub_current.name == 'ul' else "numbered_list"
                            subsection_content_parts.append({
                                "type": tag_type,
                                "items": items
                            })
                        sub_current = sub_current.find_next_sibling()
                    
                    current_slide_content["subsections"].append({
                        "heading": subsection_title,
                        "content": subsection_content_parts
                    })
                    
                    # Usually 1 subsection per slide is enough info
                    if len(current_slide_content["subsections"]) >= MAX_SUBSECTIONS_PER_SLIDE:
                        commit_current_slide(part_counter)
                        part_counter += 1
                    
                    # Skip 'current' forward to where sub_current stopped
                    current = sub_current
                    continue

                elif current.name == 'p':
                    text = current.get_text(strip=True)
                    if text:
                        if paragraph_count >= MAX_PARAGRAPHS_PER_SLIDE and bullet_count > 0:
                            # Mixed content getting full
                            should_break_slide = True
                        elif paragraph_count >= MAX_PARAGRAPHS_PER_SLIDE * 2:
                             # Pure text getting too long
                             should_break_slide = True
                        
                        if should_break_slide:
                            commit_current_slide(part_counter)
                            part_counter += 1
                            should_break_slide = False
                        
                        current_slide_content["paragraphs"].append(text)
                        current_slide_content["content_parts"].append({
                            "type": "paragraph",
                            "text": text
                        })
                        paragraph_count += 1
                        
                elif current.name in ['ul', 'ol']:
                    items = [li.get_text(strip=True) for li in current.find_all('li')]
                    if items:
                        new_bullet_count = len(items)
                        
                        if bullet_count + new_bullet_count > MAX_BULLETS_PER_SLIDE and (paragraph_count > 0 or bullet_count > 0):
                             should_break_slide = True
                        
                        if should_break_slide:
                             commit_current_slide(part_counter)
                             part_counter += 1
                             should_break_slide = False

                        current_slide_content["bullet_points"].extend(items)
                        tag_type = "bullet_list" if current.name == 'ul' else "numbered_list"
                        current_slide_content["content_parts"].append({
                            "type": tag_type,
                            "items": items
                        })
                        bullet_count += new_bullet_count

                elif current.name in ['strong', 'em', 'b', 'i']:
                    text = current.get_text(strip=True)
                    if text:
                        current_slide_content["content_parts"].append({
                            "type": "emphasis",
                            "text": text
                        })

                current = current.find_next_sibling()
            
            # Commit whatever is left for this h2 section
            commit_current_slide(part_counter)
            
        logger.info(f"[NOTES-PARSER] Created {len(slides)} slides from HTML notes with pagination")
        return slides
        
    except Exception as e:
        logger.error(f"[NOTES-PARSER] Error parsing HTML: {e}")
        # Fallback
        return [{
            "id": f"slide-{start_slide_num}",
            "type": "notes_section",
            "layout": "text_only",
            "content": {
                "title": "Simplified Lesson Notes",
                "html_content": html_content
            }
        }]


def _build_student_pack_slides(
    subject: str,
    class_name: str,
    topic: str,
    notes_html: str,
    videos: List[Dict],
    audio_url: str,
    audio_duration: int,
    mcq_questions: List[Dict],
    essay_questions: List[Dict],
    slide_images: List[Dict] = None
) -> Dict:
    """
    Build a structured slide-format student pack.
    
    Structure:
    1. Title slide
    2. Visual Resources slides (images from teacher's slides)
    3. Notes slides (simplified content)
    4. Video resource slides
    5. Podcast slide
    6. Assessment slides (questions only - NO answers)
    7. Answer key slides (at the very end)
    """
    from uuid import uuid4
    
    slides = []
    slide_num = 1
    
    # === 1. Title Slide ===
    slides.append({
        "id": f"slide-{slide_num}",
        "type": "title",
        "layout": "title_center",
        "content": {
            "title": f"Student Learning Pack: {topic}",
            "subtitle": f"{subject} - {class_name}"
        }
    })
    slide_num += 1
    
    # === 2. Visual Resources Gallery (All images from teacher's slides) ===
    if slide_images:
        # Create a single gallery slide with all images
        image_items = []
        for img in slide_images:
            image_items.append({
                "gcs_path": img.get("gcs_path"),
                "alt_text": img.get("alt_text", "Educational diagram"),
                "caption": img.get("alt_text", "Diagram")
            })
        
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "visual_gallery",
            "layout": "image_grid",
            "content": {
                "title": "Key Diagrams & Visual Aids",
                "description": "These diagrams illustrate the key concepts in this lesson.",
                "images": image_items
            }
        })
        slide_num += 1
    
    # === 3. Notes Slides (Parse HTML into structured slides) ===
    if notes_html:
        notes_slides = _parse_html_to_slides(notes_html, slide_num)
        slides.extend(notes_slides)
        slide_num += len(notes_slides)

    
    # === 4. Video Resource Slides ===
    if videos:
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "video_resources",
            "layout": "video_grid",
            "content": {
                "title": "Recommended Videos",
                "description": "Watch these videos to learn more about this topic!",
                "videos": videos
            }
        })
        slide_num += 1
    
    # === 4. Podcast Slide ===
    if audio_url:
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "podcast",
            "layout": "audio_player",
            "content": {
                "title": "Listen & Learn Podcast",
                "description": "A 10-minute conversation about this lesson with ALEX and SAM!",
                "audio_url": audio_url,
                "duration_ms": audio_duration
            }
        })
        slide_num += 1
    
    # === 5. Assessment Slides (Questions Only - NO Answers) ===
    # Paginate MCQs: 5 questions per slide
    MCQ_PER_SLIDE = 5
    ESSAY_PER_SLIDE = 2
    
    if mcq_questions:
        # Split into chunks
        for chunk_idx in range(0, len(mcq_questions), MCQ_PER_SLIDE):
            chunk = mcq_questions[chunk_idx:chunk_idx + MCQ_PER_SLIDE]
            chunk_num = (chunk_idx // MCQ_PER_SLIDE) + 1
            total_chunks = (len(mcq_questions) + MCQ_PER_SLIDE - 1) // MCQ_PER_SLIDE
            
            # Remove answers for student view
            questions_only = []
            for q in chunk:
                questions_only.append({
                    "question": q.get("question", ""),
                    "options": q.get("options", []),
                    "question_number": mcq_questions.index(q) + 1  # Global question number
                    # Note: correct_answer and explanation are NOT included
                })
            
            title_suffix = f" (Part {chunk_num}/{total_chunks})" if total_chunks > 1 else ""
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "assessment_mcq",
                "layout": "assessment",
                "content": {
                    "title": f"Test Your Knowledge - Multiple Choice{title_suffix}",
                    "instructions": "Choose the best answer for each question.",
                    "questions": questions_only,
                    "part": chunk_num,
                    "total_parts": total_chunks
                }
            })
            slide_num += 1
    
    if essay_questions:
        # Split into chunks
        for chunk_idx in range(0, len(essay_questions), ESSAY_PER_SLIDE):
            chunk = essay_questions[chunk_idx:chunk_idx + ESSAY_PER_SLIDE]
            chunk_num = (chunk_idx // ESSAY_PER_SLIDE) + 1
            total_chunks = (len(essay_questions) + ESSAY_PER_SLIDE - 1) // ESSAY_PER_SLIDE
            
            # Remove key_points for student view
            questions_only = []
            for q in chunk:
                questions_only.append({
                    "question": q.get("question", ""),
                    "marks": q.get("marks", 10),
                    "question_number": essay_questions.index(q) + 1  # Global question number
                    # Note: key_points are NOT included
                })
            
            title_suffix = f" (Part {chunk_num}/{total_chunks})" if total_chunks > 1 else ""
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "assessment_essay",
                "layout": "assessment",
                "content": {
                    "title": f"Test Your Knowledge - Essay Questions{title_suffix}",
                    "instructions": "Answer the following questions in detail.",
                    "questions": questions_only,
                    "part": chunk_num,
                    "total_parts": total_chunks
                }
            })
            slide_num += 1
    
    # === 6. Answer Key Slides (At the End) ===
    # Paginate answer keys to match question slides
    if mcq_questions:
        for chunk_idx in range(0, len(mcq_questions), MCQ_PER_SLIDE):
            chunk = mcq_questions[chunk_idx:chunk_idx + MCQ_PER_SLIDE]
            chunk_num = (chunk_idx // MCQ_PER_SLIDE) + 1
            total_chunks = (len(mcq_questions) + MCQ_PER_SLIDE - 1) // MCQ_PER_SLIDE
            
            mcq_answers = []
            for q in chunk:
                mcq_answers.append({
                    "question_number": mcq_questions.index(q) + 1,
                    "question": q.get("question", "")[:100] + ("..." if len(q.get("question", "")) > 100 else ""),
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", "")
                })
            
            title_suffix = f" (Part {chunk_num}/{total_chunks})" if total_chunks > 1 else ""
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "answer_key_mcq",
                "layout": "answer_key",
                "content": {
                    "title": f"Answer Key - Multiple Choice{title_suffix}",
                    "note": "Compare your answers with the correct answers below.",
                    "answers": mcq_answers,
                    "part": chunk_num,
                    "total_parts": total_chunks
                }
            })
            slide_num += 1
    
    if essay_questions:
        for chunk_idx in range(0, len(essay_questions), ESSAY_PER_SLIDE):
            chunk = essay_questions[chunk_idx:chunk_idx + ESSAY_PER_SLIDE]
            chunk_num = (chunk_idx // ESSAY_PER_SLIDE) + 1
            total_chunks = (len(essay_questions) + ESSAY_PER_SLIDE - 1) // ESSAY_PER_SLIDE
            
            essay_answers = []
            for q in chunk:
                essay_answers.append({
                    "question_number": essay_questions.index(q) + 1,
                    "question": q.get("question", "")[:100] + ("..." if len(q.get("question", "")) > 100 else ""),
                    "key_points": q.get("key_points", []),
                    "marks": q.get("marks", 10)
                })
            
            title_suffix = f" (Part {chunk_num}/{total_chunks})" if total_chunks > 1 else ""
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "answer_key_essay",
                "layout": "answer_key",
                "content": {
                    "title": f"Answer Key - Essay Questions{title_suffix}",
                    "note": "Your answers should include these key points.",
                    "answers": essay_answers,
                    "part": chunk_num,
                    "total_parts": total_chunks
                }
            })
            slide_num += 1

    
    return {
        "pack_id": str(uuid4()),
        "subject": subject,
        "class_level": class_name,
        "topic": topic,
        "generated_at": datetime.utcnow().isoformat(),
        "slides": slides,
        "summary": {
            "total_slides": len(slides),
            "has_notes": bool(notes_html),
            "image_count": len(slide_images) if slide_images else 0,
            "video_count": len(videos),
            "has_podcast": bool(audio_url),
            "podcast_duration_ms": audio_duration,
            "mcq_count": len(mcq_questions),
            "essay_count": len(essay_questions)
        }
    }


async def _synthesize_podcast_audio_with_duration(script: List[Dict], pack_id: str, teacher_id: str, session_id: str) -> tuple:
    """Synthesize audio and return URL with duration."""
    audio_url = await _synthesize_podcast_audio(script, pack_id, teacher_id, session_id)
    # Duration is calculated during synthesis - we'll estimate based on script length
    # Assuming ~150 words per minute, ~1 word per 400ms
    word_count = sum(len(item.get("text", "").split()) for item in script)
    estimated_duration_ms = word_count * 400  # 400ms per word average
    return audio_url, estimated_duration_ms


async def _update_pack_entry_with_json(pack_id, notes, videos, audio_url, content_json, status):
    """Update pack with generated content including structured JSON."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        await db.execute(
            text("""
                UPDATE student_lesson_packs 
                SET simplified_notes = :notes,
                    video_resources = :videos,
                    podcast_audio_url = :audio,
                    content_json = CAST(:content_json AS jsonb),
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id": pack_id,
                "notes": notes,
                "videos": json.dumps(videos) if videos else '[]',
                "audio": audio_url,
                "content_json": json.dumps(content_json) if content_json else '{}',
                "status": status
            }
        )
        await db.commit()
    finally:
        await db_gen.aclose()


async def _fetch_slide_content(slide_id: str) -> Optional[str]:
    """Fetch and combine slide content for context."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("SELECT content_json FROM slides WHERE id = CAST(:id AS uuid)"),
            {"id": slide_id}
        )
        row = result.fetchone()
        if not row:
            return None
            
        content_json = row._mapping["content_json"]
        
        # Combine slides into a single text block
        text_content = ""
        for slide in content_json.get("slides", []):
            title = slide.get("title", "")
            bullets = "\n".join([f"- {b}" for b in slide.get("bullet_points", [])])
            content = slide.get("content", "")
            text_content += f"\n## {title}\n{bullets}\n{content}\n"
            
        return text_content
    finally:
        await db_gen.aclose()


async def _create_initial_pack_entry(teacher_id, session_id, slide_id, subject, class_name):
    """Create pending entry in DB."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        # Check if exists first
        check = await db.execute(
            text("SELECT id FROM student_lesson_packs WHERE teacher_id = CAST(:tid AS uuid) AND session_id = :sid"),
            {"tid": teacher_id, "sid": int(session_id)}
        )
        existing = check.fetchone()
        
        if existing:
            pack_id = existing._mapping["id"]
            # Update status AND slide_id to match new slide
            await db.execute(
                text("UPDATE student_lesson_packs SET slide_id = CAST(:slide_id AS uuid), status = 'processing', updated_at = CURRENT_TIMESTAMP WHERE id = :id"),
                {"id": pack_id, "slide_id": slide_id}
            )
            await db.commit()
            return str(pack_id)

        
        # Create new
        result = await db.execute(
            text("""
                INSERT INTO student_lesson_packs 
                (teacher_id, session_id, slide_id, subject, class_name, status)
                VALUES (CAST(:tid AS uuid), :sid, CAST(:slid AS uuid), :subj, :cls, 'processing')
                RETURNING id
            """),
            {
                "tid": teacher_id, "sid": int(session_id), "slid": slide_id,
                "subj": subject, "cls": class_name
            }
        )
        pack_id = result.scalar()
        await db.commit()
        return str(pack_id)
    except Exception as e:
        logger.error(f"Failed to create pack entry: {e}")
        return None
    finally:
        await db_gen.aclose()


async def _update_pack_entry(pack_id, notes, videos, audio_url, status):
    """Update pack with generated content."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        await db.execute(
            text("""
                UPDATE student_lesson_packs 
                SET simplified_notes = :notes,
                    video_resources = :videos,
                    podcast_audio_url = :audio,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "id": pack_id,
                "notes": notes,
                "videos": json.dumps(videos) if videos else '[]',
                "audio": audio_url,
                "status": status
            }
        )
        await db.commit()
    finally:
        await db_gen.aclose()


async def _get_teacher_country(teacher_id: str) -> Optional[str]:
    """Fetch teacher's country from their profile."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("SELECT country FROM teacherprofile WHERE id = CAST(:tid AS uuid)"),
            {"tid": teacher_id}
        )
        row = result.fetchone()
        if row and row._mapping.get("country"):
            return row._mapping["country"]
        return None
    except Exception as e:
        logger.warning(f"Could not fetch teacher country: {e}")
        return None
    finally:
        await db_gen.aclose()


async def _get_session_indicator(session_id: str, teacher_id: str) -> Optional[str]:
    """Fetch the indicator text for this session."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        # Query using session_details JSONB field with containment operator
        # This matches the logic used in slide_processor.py
        result = await db.execute(
            text("""
                SELECT indicator_text 
                FROM indicator 
                WHERE teacher_id = CAST(:tid AS uuid) 
                AND session_details IS NOT NULL
                AND session_details @> :session_json
                LIMIT 1
            """),
            {
                "tid": teacher_id, 
                "session_json": json.dumps([{"id": int(session_id)}])
            }
        )
        row = result.fetchone()
        if row and row._mapping.get("indicator_text"):
            return row._mapping["indicator_text"]
        return None
    except Exception as e:
        logger.warning(f"Could not fetch session indicator: {e}")
        return None
    finally:
        await db_gen.aclose()


async def _get_education_system(teacher_id: str, subject: str, class_name: str) -> Optional[str]:
    """Fetch education system from weeklytimetable for this subject/class."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("""
                SELECT edu_sys
                FROM weeklytimetable
                WHERE teacher_id = CAST(:tid AS uuid)
                  AND subject = :subj
                  AND (pupils = :cls OR pupils ILIKE :cls_pattern)
                LIMIT 1
            """),
            {
                "tid": teacher_id,
                "subj": subject,
                "cls": class_name,
                "cls_pattern": f"%{class_name}%"
            }
        )
        row = result.fetchone()
        if row and row._mapping.get("edu_sys"):
            return row._mapping["edu_sys"]
        return None
    except Exception as e:
        logger.warning(f"Could not fetch education system: {e}")
        return None
    finally:
        await db_gen.aclose()


async def _get_education_level(teacher_id: str, subject: str, class_name: str) -> Optional[str]:
    """Fetch education level from weeklytimetable for this subject/class."""
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        result = await db.execute(
            text("""
                SELECT edu_lvl
                FROM weeklytimetable
                WHERE teacher_id = CAST(:tid AS uuid)
                  AND subject = :subj
                  AND (pupils = :cls OR pupils ILIKE :cls_pattern)
                LIMIT 1
            """),
            {
                "tid": teacher_id,
                "subj": subject,
                "cls": class_name,
                "cls_pattern": f"%{class_name}%"
            }
        )
        row = result.fetchone()
        if row and row._mapping.get("edu_lvl"):
            return row._mapping["edu_lvl"]
        return None
    except Exception as e:
        logger.warning(f"Could not fetch education level: {e}")
        return None
    finally:
        await db_gen.aclose()


# --- AI / CONTENT GENERATION ---

async def _call_vertex_ai(prompt: str, retries: int = 3) -> str:
    """Helper to call Vertex AI with retries."""
    
    try:
        # Auth logic inlined below
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        creds.refresh(Request())
        access_token = creds.token
        
        project_id = settings.GCS_PROJECT_ID
        model_id = "gemini-2.5-flash"  # Revert to 2.5-flash as 1.5 was 404
        url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generation_config": {
                "temperature": 0.4,
                "maxOutputTokens": 8192
            }
        }
        
        for attempt in range(retries + 1):
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            return data["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            return ""
                    
                    elif response.status == 429:
                        # Rate limit
                        if attempt < retries:
                            wait_time = (2 ** attempt) * 2  # 2, 4, 8 seconds
                            logger.warning(f"[WARN] Vertex AI Rate Limit (429). Waiting {wait_time}s to retry...")
                            print(f"DEBUG: Vertex AI Rate Limit. Waiting {wait_time}s...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"Vertex AI Error 429: Resource exhausted after {retries} retries.")
                            return ""
                    else:
                        error_text = await response.text()
                        logger.error(f"Vertex AI Error {response.status}: {error_text}")
                        return ""
                        
    except Exception as e:
        logger.error(f"Vertex AI Call Failed: {e}")
        return ""
                    
    except Exception as e:
        logger.error(f"Vertex AI Call Failed: {e}")
        return ""


async def _generate_simplified_notes(content: str, subject: str, class_name: str) -> str:
    """Generate ELI10 notes."""
    logger.info("[INFO] Generating simplified notes...")
    prompt = f"""
    You are an expert teacher for {class_name}.
    Rewrite the following lesson content for a 10-year-old student.
    
    Subject: {subject}
    
    Rules:
    1. Use simple, fun, and engaging language.
    2. Use analogies to explain complex concepts.
    3. Break it down into sections with emojis.
    4. Include a "Did You Know?" fun fact section.
    5. Be encouraging and supportive.
    6. Output as clean HTML (body content only, no html/head tags). Use h2, h3, p, ul, li tags.
    
    Lesson Content:
    {content[:10000]}
    """
    return await _call_vertex_ai(prompt)


async def _generate_notes_and_videos(
    slides_content: str,
    original_slides: List[Dict],
    subject: str,
    class_name: str,
    indicator: Optional[str] = None,
    education_level: Optional[str] = None,
    education_system: Optional[str] = None,
    country: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate simplified notes AND fetch real video recommendations.
    
    1. AI generates simplified notes (ELI10 style)
    2. Real YouTube search finds actual videos
    3. AI ranks the real videos for educational relevance
    
    Returns:
        {
            "notes_html": "<h2>...</h2>...",
            "videos": [
                {
                    "title": "...",
                    "url": "https://youtube.com/watch?v=...",
                    "channel": "...",
                    "duration": "...",
                    "description": "..."
                },
                ...
            ]
        }
    """
    logger.info("[AI-COMBINED] Generating notes and fetching real videos...")
    
    # Build detailed context for the AI
    context_parts = [
        f"Subject: {subject}",
        f"Class Level: {class_name}",
    ]
    
    if education_level:
        context_parts.append(f"Education Level: {education_level}")
    
    if education_system:
        context_parts.append(f"Curriculum/Education System: {education_system}")
    
    if country:
        context_parts.append(f"Country: {country}")
    
    if indicator:
        context_parts.append(f"Learning Objective: {indicator}")
    
    context = "\n".join(context_parts)
    
    # Extract DETAILED content from slides (not just titles)
    slide_details = []
    for idx, slide in enumerate(original_slides):
        slide_type = slide.get("type", "")
        # Skip assessment slides
        if slide_type in ["assessment_mcq", "assessment_essay", "title"]:
            continue
            
        content = slide.get("content", {})
        title = content.get("title", "") or content.get("heading", "")
        bullet_points = content.get("bullet_points", [])
        
        if title or bullet_points:
            slide_info = f"\n--- SLIDE {idx + 1}: {title} ---"
            if bullet_points:
                for point in bullet_points[:6]:  # Max 6 points per slide
                    slide_info += f"\n• {point}"
            slide_details.append(slide_info)
    
    slides_content_structured = "\n".join(slide_details[:12]) if slide_details else slides_content[:6000]
    
    # STEP 1: Generate TEACHING-FOCUSED notes (not summaries)
    notes_prompt = f"""You are a friendly teacher explaining lesson slides to students.
Your job is NOT to summarize, but to TEACH in simple language that students can understand.

STUDENT CONTEXT:
{context}

THE LESSON SLIDES TO EXPLAIN:
{slides_content_structured}

ADDITIONAL LESSON CONTENT:
{slides_content[:4000]}

YOUR TASK - TEACH EACH CONCEPT:
For EACH major concept/point from the slides above, you must:

1. STATE THE MAIN IDEA - One clear sentence explaining what this concept is about
2. EXPLAIN STEP-BY-STEP - Break down the concept in simple language (imagine explaining to a younger sibling)
3. GIVE AN EVERYDAY EXAMPLE - Use a relatable real-world example the student can connect with
4. COMMON MISTAKE - Explain one mistake students often make about this topic
5. PRACTICE QUESTIONS - Ask 2 short questions to check understanding
6. ANSWERS - Provide clear answers to the practice questions

CRITICAL RULES:
1. NO EMOJIS - Do not use any emoji characters whatsoever
2. Use UNIVERSALLY RELATABLE examples (water, cooking, running, animals, sun, rain, markets, family) 
   - AVOID: LEGOs, video games, brand names, Western-specific references
3. Do NOT copy text directly from slides - TEACH it like you're speaking to a student
4. Be encouraging and supportive ("Great question!", "You're doing well!")
5. Use simple vocabulary appropriate for the class level
6. Make connections between concepts where possible

OUTPUT HTML STRUCTURE:
- Use h2 for each major topic/concept being explained
- Use h3 for subsections (Main Idea, Step-by-Step, Example, Common Mistake, Practice Questions, Answers)
- Use p for paragraphs
- Use ul/li for lists and bullet points
- Use strong for key terms
- NO html/head/body tags - just content tags

EXAMPLE OUTPUT STRUCTURE (follow this pattern for each concept):

<h2>Understanding Electric Charge</h2>

<h3>Main Idea</h3>
<p>Electric charge is a property of tiny particles that makes them attract or push away from each other.</p>

<h3>Step-by-Step Explanation</h3>
<p>Let me explain this step by step...</p>
<ul>
<li><strong>First:</strong> Everything around us is made of tiny particles called atoms...</li>
<li><strong>Second:</strong> Inside atoms, there are even tinier particles...</li>
<li><strong>Third:</strong> These particles have a special property called charge...</li>
</ul>

<h3>Everyday Example</h3>
<p>Think about what happens when you rub a balloon on your hair...</p>

<h3>Common Mistake</h3>
<p>Many students think that... but actually...</p>

<h3>Practice Questions</h3>
<ul>
<li>Question 1: What are the two types of electric charge?</li>
<li>Question 2: What happens when two negative charges come close together?</li>
</ul>

<h3>Answers</h3>
<ul>
<li>Answer 1: The two types are positive and negative charge.</li>
<li>Answer 2: They push away (repel) each other.</li>
</ul>

[Continue this pattern for each major concept...]

<h2>Did You Know?</h2>
<p>Here's an amazing fact about this topic...</p>

OUTPUT FORMAT:
- Return ONLY the raw HTML content
- Start directly with <h2> tags
- NO JSON wrapping
- NO markdown code blocks
- NO explanations before or after the HTML
- ABSOLUTELY NO EMOJIS
- Cover ALL major concepts from the slides
"""

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        # Initialize Vertex AI
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        project_id = service_account_info.get("project_id")
        
        vertexai.init(
            project=project_id,
            location="us-central1",
            credentials=service_account.Credentials.from_service_account_info(service_account_info)
        )
        
        model = GenerativeModel("gemini-2.0-flash-exp")
        
        logger.info("[AI-NOTES] Calling Gemini for notes generation...")
        
        response = model.generate_content(
            notes_prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 8192,  # Increased for detailed teaching notes
            }
        )
        
        response_text = response.text.strip()
        
        # Extract HTML from response (remove any markdown code blocks)
        if "```html" in response_text:
            response_text = response_text.split("```html")[1].split("```")[0].strip()
        elif "```" in response_text:
            # Remove any code block formatting
            parts = response_text.split("```")
            if len(parts) >= 3:
                response_text = parts[1].strip()
            else:
                response_text = response_text.replace("```", "").strip()
        
        # The response should be raw HTML now - validate it has HTML content
        notes_html = response_text
        
        # Basic validation - check if it looks like HTML
        if not notes_html.startswith("<"):
            # Try to find the first HTML tag
            import re
            html_match = re.search(r'<h[1-6].*?>', notes_html, re.IGNORECASE)
            if html_match:
                notes_html = notes_html[html_match.start():]
            else:
                logger.warning("[AI-NOTES] Response does not look like HTML, using as-is")
        
        logger.info(f"[AI-NOTES] Generated {len(notes_html)} chars of notes")
        
        # STEP 2: Search for REAL YouTube videos
        search_topic = indicator if indicator else f"{subject} {class_name}"
        videos = await _search_and_rank_youtube_videos(
            topic=search_topic,
            subject=subject,
            class_name=class_name,
            education_level=education_level,
            model=model  # Pass the model for ranking
        )
        
        logger.info(f"[VIDEOS] Got {len(videos)} verified real video URLs")
        
        return {
            "notes_html": notes_html,
            "videos": videos
        }
        
    except Exception as e:
        logger.error(f"[AI-COMBINED] AI call failed: {e}")
        raise  # Re-raise for retry logic


async def _search_and_rank_youtube_videos(
    topic: str,
    subject: str,
    class_name: str,
    education_level: Optional[str] = None,
    model = None,
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """
    Search YouTube for REAL videos and have AI rank them for educational relevance.
    
    This ensures we only return working links (not hallucinated).
    
    Args:
        topic: The learning objective or topic to search for
        subject: Subject name
        class_name: Class level
        education_level: Education level (e.g., "SHS", "JHS")
        model: Vertex AI model for ranking
        max_results: Maximum number of videos to return
    
    Returns:
        List of verified video objects with real URLs
    """
    logger.info(f"[YOUTUBE] Searching for real videos about: {topic[:80]}...")
    
    try:
        from youtubesearchpython import VideosSearch
        
        # Build search queries - multiple queries for better coverage
        search_queries = [
            f"{subject} {topic[:50]} educational",
            f"{topic[:50]} explained for students",
            f"{subject} lesson {class_name}",
        ]
        
        # Add educational channel prefixes
        educational_channels = ["Khan Academy", "CrashCourse", "TED-Ed", "Bozeman Science"]
        search_queries.append(f"{educational_channels[0]} {subject} {topic[:30]}")
        
        all_videos = []
        seen_ids = set()
        
        for query in search_queries:
            try:
                logger.info(f"[YOUTUBE] Searching: {query[:60]}...")
                search = VideosSearch(query, limit=8)
                results = search.result()
                
                for video in results.get("result", []):
                    video_id = video.get("id", "")
                    
                    # Skip duplicates
                    if video_id in seen_ids:
                        continue
                    seen_ids.add(video_id)
                    
                    # Skip shorts and very long videos
                    duration_str = video.get("duration", "0:00") or "0:00"
                    duration_seconds = _parse_duration(duration_str)
                    
                    # Skip videos < 1 min or > 30 min
                    if duration_seconds < 60 or duration_seconds > 1800:
                        continue
                    
                    # Build video object
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    all_videos.append({
                        "id": video_id,
                        "title": video.get("title", ""),
                        "url": video_url,
                        "channel": video.get("channel", {}).get("name", "Unknown"),
                        "duration": duration_str,
                        "views": video.get("viewCount", {}).get("text", ""),
                        "description": video.get("descriptionSnippet", [{}])[0].get("text", "") if video.get("descriptionSnippet") else "",
                        "thumbnail": video.get("thumbnails", [{}])[0].get("url", "") if video.get("thumbnails") else "",
                        "type": "video"
                    })
                    
            except Exception as e:
                logger.warning(f"[YOUTUBE] Search query failed: {e}")
                continue
        
        if not all_videos:
            logger.warning("[YOUTUBE] No videos found")
            return []
        
        logger.info(f"[YOUTUBE] Found {len(all_videos)} candidate videos")
        
        # STEP 3: Have AI rank the videos for educational relevance
        if model and len(all_videos) > max_results:
            ranked_videos = await _ai_rank_videos(
                videos=all_videos,
                topic=topic,
                subject=subject,
                education_level=education_level,
                model=model,
                top_n=max_results
            )
            return ranked_videos
        else:
            # Return top videos by view count or just first N
            return all_videos[:max_results]
        
    except ImportError:
        logger.error("[YOUTUBE] youtube-search-python not installed!")
        return []
    except Exception as e:
        logger.error(f"[YOUTUBE] Search failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


async def _ai_rank_videos(
    videos: List[Dict],
    topic: str,
    subject: str,
    education_level: Optional[str],
    model,
    top_n: int = 5
) -> List[Dict]:
    """
    Use AI to rank videos by educational relevance.
    
    Args:
        videos: List of video objects from YouTube search
        topic: The learning objective
        subject: Subject name
        education_level: Target education level
        model: Vertex AI GenerativeModel
        top_n: Number of top videos to return
    
    Returns:
        List of top-ranked video objects
    """
    logger.info(f"[AI-RANK] Ranking {len(videos)} videos for relevance...")
    
    # Format videos for AI
    video_list = []
    for i, v in enumerate(videos):
        video_list.append(f"""
Video {i+1}:
- Title: {v.get('title', '')[:100]}
- Channel: {v.get('channel', '')}
- Duration: {v.get('duration', '')}
- Description: {v.get('description', '')[:150]}
""")
    
    videos_text = "\n".join(video_list)
    
    ranking_prompt = f"""You are an educational content curator. Rank these YouTube videos by their educational relevance for students learning about:

TOPIC: {topic}
SUBJECT: {subject}
LEVEL: {education_level or 'General'}

VIDEOS TO RANK:
{videos_text}

RANKING CRITERIA:
1. Educational value (explains concepts clearly)
2. Appropriate for students (no inappropriate content)
3. From reputable educational channels (Khan Academy, CrashCourse, TED-Ed, etc.)
4. Matches the topic and learning objective
5. Good duration (5-15 minutes ideal)

RETURN ONLY the video numbers of the TOP {top_n} videos in order of relevance.
Format: [1, 5, 3, 7, 2]

Just return the JSON array of numbers, nothing else.
"""

    try:
        response = model.generate_content(
            ranking_prompt,
            generation_config={
                "temperature": 0.3,  # Lower temp for more consistent ranking
                "max_output_tokens": 256,
            }
        )
        
        response_text = response.text.strip()
        
        # Extract array
        if "[" in response_text and "]" in response_text:
            start = response_text.index("[")
            end = response_text.rindex("]") + 1
            array_text = response_text[start:end]
            ranked_indices = json.loads(array_text)
            
            # Get videos in ranked order
            ranked_videos = []
            for idx in ranked_indices:
                video_idx = int(idx) - 1  # Convert to 0-based index
                if 0 <= video_idx < len(videos):
                    ranked_videos.append(videos[video_idx])
            
            logger.info(f"[AI-RANK] Selected {len(ranked_videos)} top videos")
            return ranked_videos[:top_n]
        else:
            logger.warning("[AI-RANK] Could not parse ranking response")
            return videos[:top_n]
            
    except Exception as e:
        logger.warning(f"[AI-RANK] Ranking failed: {e}, returning unranked")
        return videos[:top_n]


def _parse_duration(duration_str: str) -> int:
    """Parse YouTube duration string to seconds."""
    try:
        parts = duration_str.split(":")
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return 0
    except:
        return 0






async def _generate_podcast_script(notes: str) -> str:
    """Generate a dialogue script for TTS."""
    logger.info("[INFO] Generating podcast script (10-minute version)...")
    prompt = f"""
    Convert these lesson notes into a lively, engaging 10-MINUTE podcast script between two hosts:
    ALEX (Energetic, exciting, explains concepts clearly) and SAM (Curious, asks thoughtful questions, summarizes key points).
    
    IMPORTANT: The script MUST be detailed enough for 10 minutes of audio. This means:
    - At least 40-50 exchanges between the hosts
    - Each response should be 2-4 sentences on average
    - Cover ALL key concepts from the notes in detail
    - Include examples and analogies
    - Add recap sections every few minutes
    - End with a summary of the top 3 takeaways
    
    Structure the conversation like this:
    1. Introduction (30 seconds): Hook the listener, introduce the topic
    2. Main Content (8 minutes): Deep dive into each concept with examples
    3. Summary & Takeaways (1.5 minutes): Recap the most important points
    
    Format the output EXACTLY as a JSON list of objects:
    [
        {{"speaker": "ALEX", "text": "..."}},
        {{"speaker": "SAM", "text": "..."}}
    ]
    
    Keep it conversational, use simple student-friendly language, and make it sound like a real engaging chat.
    
    Cover ALL the main points from these notes thoroughly:
    {notes[:15000]}
    """
    response_text = await _call_vertex_ai(prompt)
    
    # Extract JSON
    try:
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if json_match:
            script = json.loads(json_match.group(0))
            logger.info(f"[INFO] Generated podcast script with {len(script)} dialogue lines")
            return script
        return []
    except Exception as e:
        logger.error(f"Failed to parse podcast script JSON: {e}")
        return []




# ============================================================================
# Cloud Text-to-Speech API with Gemini TTS (Primary Method - Direct MP3 Output)
# ============================================================================

def _generate_audio_with_tts_api(text: str, speaker: str) -> Optional[bytes]:
    """
    Generate audio using Cloud Text-to-Speech API with Gemini TTS models.
    
    This method directly outputs MP3 and is the preferred method.
    Uses the pre-initialized TTS_CLIENT.
    
    Args:
        text: Text to convert to speech
        speaker: Speaker name (ALEX = male/Sadachbia, others = female/Sulafat)
        
    Returns:
        MP3 audio bytes or None if failed
    """
    global TTS_CLIENT
    
    if not TTS_AVAILABLE or TTS_CLIENT is None:
        logger.warning("[WARN] TTS client not available, falling back to Vertex AI REST API")
        return None
    
    max_retries = 2  # Allow one retry after credential refresh
    
    for attempt in range(max_retries):
        try:
            from google.cloud import texttospeech
            
            # Voice selection: Sadachbia (male) for ALEX, Sulafat (female) for SAM
            is_male = "ALEX" in speaker.upper()
            voice_name = "Sadachbia" if is_male else "Sulafat"
            
            # Create synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Voice selection with Gemini TTS model
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name=voice_name,
                model_name="gemini-2.5-flash-tts"
            )
            
            # Audio config - Direct MP3 output
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                sample_rate_hertz=24000,
                speaking_rate=1.0,
            )
            
            logger.info(f"[TTS-API] Generating audio for {speaker} with voice {voice_name}...")
            
            # Perform synthesis
            response = TTS_CLIENT.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            if response.audio_content:
                logger.info(f"[SUCCESS] TTS API generated {len(response.audio_content)} bytes of MP3 audio")
                return response.audio_content
            else:
                logger.error("[ERROR] TTS API returned empty audio content")
                return None
                
        except Exception as e:
            error_str = str(e)
            
            # Check for token expiration errors
            if "ACCESS_TOKEN_EXPIRED" in error_str or "authentication credentials" in error_str:
                if attempt < max_retries - 1:
                    logger.warning("[TTS] Token expired, refreshing credentials...")
                    if _refresh_tts_client():
                        continue  # Retry with new credentials
                    else:
                        logger.error("[ERROR] Failed to refresh TTS credentials")
                        return None
            
            logger.error(f"[ERROR] TTS API synthesis failed: {e}")
            return None
    
    return None



async def _generate_audio_with_gemini_flash(text: str, speaker: str, max_retries: int = 5) -> Optional[bytes]:
    """
    Generate audio using Gemini 2.5 Flash TTS with retry logic.
    
    Args:
        text: Text to convert to speech
        speaker: Speaker name (ALEX = male, others = female)
        max_retries: Maximum retry attempts for transient errors
        
    Returns:
        Audio bytes or None if failed
    """
    
    # helper for auth
    async def _get_headers():
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        creds.refresh(Request())
        return {
            "Authorization": f"Bearer {creds.token}",
            "Content-Type": "application/json"
        }

    project_id = settings.GCS_PROJECT_ID
    
    # Specific voices: Male = Sadachbia (ALEX), Female = Sulafat (SAM)
    is_male = "ALEX" in speaker
    voice_name = "Sadachbia" if is_male else "Sulafat"
    
    model_id = "gemini-2.5-flash-tts"
    url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:generateContent"
    
    # Payload for Gemini TTS with audio parameters
    # See: https://cloud.google.com/text-to-speech/docs/reference/rest/v1/text/synthesize
    # speech_config options:
    #   - speaking_rate: 0.25 to 4.0 (1.0 = normal, 0.25 = slowest)
    #   - sample_rate_hertz: output sample rate (e.g., 22050, 24000)
    #   - volume_gain_db: Volume gain in dB (-96.0 to 16.0)
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": text}] 
        }],
        "generation_config": {
             "response_modalities": ["AUDIO"],
             "speech_config": {
                  "voice_config": {
                      "prebuilt_voice_config": {
                          "voice_name": voice_name
                      }
                  },
                  # Audio output configuration - Gemini TTS outputs 24kHz audio
                  # Note: sample_rate_hertz may not be changeable via API
                  # speaking_rate: 1.0 = normal speed
             }
        }
    }
    
    attempt = 0
    while attempt < max_retries:
        try:
            headers = await _get_headers()
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        data = json.loads(response_text)
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "inlineData" in part:
                                    b64_data = part["inlineData"]["data"]
                                    mime_type = part["inlineData"].get("mimeType", "audio/wav")
                                    logger.info(f"[SUCCESS] Audio generated: {len(b64_data)} bytes, format: {mime_type}")
                                    return base64.b64decode(b64_data)
                                        
                            logger.warning(f"[WARN] {model_id} returned no audio data in response")
                            return None
                    
                    # Parse error message
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get('error', {}).get('message', response_text[:200])
                    except:
                        error_msg = response_text[:200]
                    
                    # Handle rate limit (429) and quota errors with exponential backoff
                    if response.status == 429 or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                        attempt += 1
                        # Exponential backoff: 10s, 20s, 40s, 80s, 160s
                        wait_time = min(10 * (2 ** attempt), 180)  # Max 3 minutes
                        logger.warning(f"[RATE LIMIT] {model_id} quota/rate limit. Waiting {wait_time}s... (Attempt {attempt}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Handle service unavailable (503)
                    elif response.status == 503 or "unavailable" in error_msg.lower():
                        attempt += 1
                        wait_time = min(15 * (2 ** attempt), 120)  # Max 2 minutes
                        logger.warning(f"[SERVICE UNAVAILABLE] {model_id}. Waiting {wait_time}s... (Attempt {attempt}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    # Handle authentication errors (don't retry)
                    elif response.status == 401 or response.status == 403:
                        logger.error(f"[AUTH ERROR] {model_id}: {error_msg}")
                        return None
                    
                    # Handle other errors
                    else:
                        attempt += 1
                        if attempt < max_retries:
                            wait_time = 5 * attempt
                            logger.warning(f"[ERROR] {model_id} status {response.status}: {error_msg}. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.error(f"[FAILED] {model_id} after {max_retries} attempts: {error_msg}")
                            return None
                            
        except asyncio.TimeoutError:
            attempt += 1
            if attempt < max_retries:
                wait_time = 10 * attempt
                logger.warning(f"[TIMEOUT] {model_id} request timed out. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                await asyncio.sleep(wait_time)
                continue
            else:
                logger.error(f"[FAILED] {model_id} timeout after {max_retries} attempts")
                return None
                
        except Exception as e:
            attempt += 1
            error_str = str(e)
            
            # Check for connection errors that might be transient
            if "connection" in error_str.lower() or "ssl" in error_str.lower():
                if attempt < max_retries:
                    wait_time = 15 * attempt
                    logger.warning(f"[CONNECTION ERROR] {model_id}: {e}. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
            
            logger.error(f"[EXCEPTION] {model_id}: {e}")
            if attempt >= max_retries:
                return None
    
    logger.error(f"[FAILED] {model_id} max retries ({max_retries}) exceeded")
    return None

async def _synthesize_podcast_audio(script: List[Dict], pack_id: str, teacher_id: str, session_id: str) -> Optional[str]:
    """
    Synthesize podcast audio maintaining conversation order.
    
    Uses smart batching: consecutive lines from the same speaker are combined 
    into one TTS call, but the dialogue order is preserved.
    
    Storage Path Structure:
        student_packs/{teacher_id}/{session_id}/podcast.mp3
    
    This ensures proper organization for multiple teachers.
    
    Example: ALEX, ALEX, SAM, ALEX, SAM, SAM
    Becomes: [ALEX batch], [SAM batch], [ALEX batch], [SAM batch]
    This is 4 API calls instead of 6, while maintaining conversation flow.
    """
    if not script:
        return None
        
    logger.info("[INFO] Synthesizing audio (conversation-ordered batching)...")
    
    try:
        from google.cloud import storage
        import tempfile
        import os
        
        # Try to import pydub
        try:
            from pydub import AudioSegment
            PYDUB_AVAILABLE = True
        except ImportError:
            logger.warning("pydub not available - audio processing will fail")
            PYDUB_AVAILABLE = False
            return None
        
        # Initialize GCS client
        if settings.GCS_SERVICE_ACCOUNT_JSON.startswith('{'):
            storage_client = storage.Client.from_service_account_info(json.loads(settings.GCS_SERVICE_ACCOUNT_JSON))
        else:
            storage_client = storage.Client.from_service_account_json(settings.GCS_SERVICE_ACCOUNT_JSON)
            
        bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
        temp_files = []
        
        # ====================================================================
        # SMART BATCHING: Batch consecutive lines from the same speaker
        # This maintains conversation order while reducing API calls
        # ====================================================================
        batches = []  # List of (speaker, combined_text)
        current_speaker = None
        current_texts = []
        
        for line in script:
            speaker = line.get("speaker", "").upper()
            text = line.get("text", "").strip()
            if not text:
                continue
            
            # Normalize speaker: ALEX for male, SAM for everyone else
            normalized_speaker = "ALEX" if "ALEX" in speaker else "SAM"
            
            if normalized_speaker == current_speaker:
                # Same speaker, add to current batch
                current_texts.append(text)
            else:
                # Different speaker, save current batch and start new one
                if current_texts and current_speaker:
                    batches.append((current_speaker, " ... ".join(current_texts)))
                current_speaker = normalized_speaker
                current_texts = [text]
        
        # Don't forget the last batch
        if current_texts and current_speaker:
            batches.append((current_speaker, " ... ".join(current_texts)))
        
        logger.info(f"[INFO] Smart batching: {len(batches)} batches from {len(script)} dialogue lines")
        
        # ====================================================================
        # Generate audio for each batch IN ORDER
        # ====================================================================
        audio_segments = []
        use_tts_api = TTS_AVAILABLE and TTS_CLIENT is not None
        
        for i, (speaker, batch_text) in enumerate(batches):
            logger.info(f"[INFO] Generating batch {i+1}/{len(batches)}: {speaker}...")
            
            audio_content = None
            
            # Try Cloud TTS API first (primary method)
            if use_tts_api:
                audio_content = await asyncio.get_event_loop().run_in_executor(
                    executor, _generate_audio_with_tts_api, batch_text, speaker
                )
                
                if audio_content:
                    # TTS API returns MP3 directly
                    temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                    temp_file.write(audio_content)
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    
                    try:
                        segment = AudioSegment.from_mp3(temp_file.name)
                        audio_segments.append(segment)
                        logger.info(f"[SUCCESS] Batch {i+1} ({speaker}): {len(segment)}ms")
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to load MP3 for batch {i+1}: {e}")
                        audio_content = None  # Reset to try fallback
            
            # Fallback to Vertex AI REST API if TTS API didn't work
            if not audio_content:
                logger.info(f"[FALLBACK] Using Vertex AI for batch {i+1}...")
                audio_content = await _generate_audio_with_gemini_flash(batch_text, speaker)
                
                if audio_content:
                    temp_file = tempfile.NamedTemporaryFile(suffix='.raw', delete=False)
                    temp_file.write(audio_content)
                    temp_file.close()
                    temp_files.append(temp_file.name)
                    
                    try:
                        segment = AudioSegment.from_raw(
                            temp_file.name,
                            sample_width=2,
                            frame_rate=24000,
                            channels=1
                        )
                        audio_segments.append(segment)
                        logger.info(f"[SUCCESS] Batch {i+1} ({speaker}): {len(segment)}ms")
                    except Exception as e:
                        logger.error(f"[ERROR] Failed to process raw audio for batch {i+1}: {e}")
        
        if not audio_segments:
            logger.error("[ERROR] No audio generated")
            return None
        
        # ====================================================================
        # Combine audio segments with pauses between speakers
        # ====================================================================
        combined = AudioSegment.empty()
        for i, segment in enumerate(audio_segments):
            combined += segment
            # Add a pause after each segment (speaker turn)
            combined += AudioSegment.silent(duration=400)  # 400ms pause
        
        # Export to MP3
        output_temp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        output_temp.close()
        temp_files.append(output_temp.name)
        
        combined.export(
            output_temp.name,
            format="mp3",
            bitrate="192k",
            parameters=["-q:a", "2"]
        )
        
        with open(output_temp.name, 'rb') as f:
            final_audio = f.read()
        
        logger.info(f"[INFO] Combined audio: {len(combined)}ms, {len(final_audio)} bytes")
        
        # Clean up temp files
        for temp_path in temp_files:
            try:
                os.unlink(temp_path)
            except Exception:
                pass
        
        # Upload to GCS with retry
        # Use structured path: student_packs/{teacher_id}/{session_id}/podcast.mp3
        blob_path = f"student_packs/{teacher_id}/{session_id}/podcast.mp3"
        blob = bucket.blob(blob_path)
        
        upload_success = False
        upload_attempts = 0
        max_upload_retries = 3
        
        while upload_attempts < max_upload_retries and not upload_success:
            try:
                upload_attempts += 1
                blob.upload_from_string(final_audio, content_type="audio/mpeg")
                upload_success = True
                logger.info(f"[SUCCESS] GCS upload successful on attempt {upload_attempts}")
            except Exception as upload_error:
                logger.warning(f"[RETRY] GCS upload failed (attempt {upload_attempts}/{max_upload_retries}): {upload_error}")
                if upload_attempts < max_upload_retries:
                    import time
                    time.sleep(2 ** upload_attempts)  # Exponential backoff: 2s, 4s, 8s
                else:
                    logger.error(f"[ERROR] GCS upload failed after {max_upload_retries} attempts")
                    return None
        
        url = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/{blob_path}"
        logger.info(f"[SUCCESS] Podcast audio uploaded: {url}")
        return url
        
    except Exception as e:
        logger.error(f"Audio synthesis/upload failed: {e}")
        import traceback
        traceback.print_exc()
        return None

