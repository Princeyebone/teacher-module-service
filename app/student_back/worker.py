"""
Student Support Worker

Background worker for processing student support pack generation requests.
Uses a queue-based worker pool with proper retries and AI initialization.

Run with: python student_back/worker.py
"""

import sys
from pathlib import Path

# Add parent directory to path so imports work when running as subprocess
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import traceback

from sqlalchemy import text
from google.oauth2 import service_account

from app.core.database import get_db
from app.core.config import settings

# Set up logging
logger = logging.getLogger("student_support_worker")
logger.setLevel(logging.INFO)

# Worker configuration
NUM_WORKERS = 2
MAX_RETRIES = 3
RETRY_DELAYS = [5, 15, 30]  # Exponential backoff for retries
POLL_INTERVAL = 10  # Seconds between polling for new jobs

# Global worker state
_workers_running = False
_worker_tasks = []
_ai_model = None
_ai_initialized = False


class StudentSupportWorker:
    """
    Background worker that processes student support pack generation requests.
    
    Features:
    - Queue-based job processing
    - Automatic retries with exponential backoff
    - Shared AI model initialization
    - Graceful shutdown
    """
    
    def __init__(self, worker_id: int):
        self.worker_id = worker_id
        self.running = False
        self.current_job = None
        self.jobs_processed = 0
        self.jobs_failed = 0
        
    async def start(self):
        """Start the worker loop."""
        self.running = True
        logger.info(f"[Worker {self.worker_id}] Started")
        
        while self.running:
            try:
                # Poll for pending jobs
                job = await self._get_next_job()
                
                if job:
                    self.current_job = job
                    await self._process_job(job)
                    self.current_job = None
                else:
                    # No jobs, wait before polling again
                    await asyncio.sleep(POLL_INTERVAL)
                    
            except asyncio.CancelledError:
                logger.info(f"[Worker {self.worker_id}] Cancelled")
                break
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Error in worker loop: {e}")
                await asyncio.sleep(POLL_INTERVAL)
        
        logger.info(f"[Worker {self.worker_id}] Stopped (Processed: {self.jobs_processed}, Failed: {self.jobs_failed})")
    
    def stop(self):
        """Stop the worker."""
        self.running = False
    
    async def _get_next_job(self) -> Optional[Dict]:
        """Get the next pending job from the database."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import async_engine
        
        async with AsyncSession(async_engine) as db:
            try:
                # Get a pending job and mark it as processing
                result = await db.execute(
                    text("""
                        UPDATE student_support_packs
                        SET status = 'processing', updated_at = CURRENT_TIMESTAMP
                        WHERE id = (
                            SELECT id FROM student_support_packs
                            WHERE status = 'pending'
                            ORDER BY created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING id, teacher_id, student_name, subject, class_name,
                                  edu_sys, edu_lvl, topic, interests, health_considerations
                    """)
                )
                row = result.fetchone()
                await db.commit()
                
                if row:
                    interests = row._mapping.get("interests") or []
                    if isinstance(interests, str):
                        interests = json.loads(interests)
                    
                    return {
                        "pack_id": str(row._mapping["id"]),
                        "teacher_id": str(row._mapping["teacher_id"]),
                        "student_name": row._mapping["student_name"],
                        "subject": row._mapping["subject"],
                        "class_name": row._mapping["class_name"],
                        "edu_sys": row._mapping.get("edu_sys"),
                        "edu_lvl": row._mapping.get("edu_lvl"),
                        "topic": row._mapping["topic"],
                        "interests": interests,
                        "health_considerations": row._mapping.get("health_considerations")
                    }
                return None
                
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Error getting job: {e}")
                await db.rollback()
                return None
    
    async def _process_job(self, job: Dict):
        """Process a single job with retries."""
        pack_id = job["pack_id"]
        student_name = job["student_name"]
        
        logger.info(f"[Worker {self.worker_id}] Processing job {pack_id} for {student_name}")
        
        for attempt in range(MAX_RETRIES):
            try:
                # Ensure AI is initialized
                await _ensure_ai_initialized()
                
                # Generate the pack content
                success = await self._generate_pack_content(job)
                
                if success:
                    logger.info(f"[Worker {self.worker_id}] Completed job {pack_id}")
                    self.jobs_processed += 1
                    return
                else:
                    raise Exception("Generation returned False")
                    
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Attempt {attempt + 1}/{MAX_RETRIES} failed for {pack_id}: {e}")
                
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.info(f"[Worker {self.worker_id}] Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    # Final failure
                    await self._mark_job_failed(pack_id, str(e))
                    self.jobs_failed += 1
    
    async def _generate_pack_content(self, job: Dict) -> bool:
        """Generate the pack content using AI."""
        global _ai_model
        
        pack_id = job["pack_id"]
        
        # Build the prompt
        interests_str = ", ".join(job["interests"]) if job["interests"] else "general learning"
        
        prompt = f"""You are an expert educational content creator specializing in personalized learning.

Create a comprehensive, personalized lesson pack for a student with specific needs.

STUDENT PROFILE:
- Name: {job["student_name"]}
- Class: {job["class_name"]}
- Education System: {job["edu_sys"] or 'Standard'}
- Education Level: {job["edu_lvl"] or 'Secondary'}
- Interests: {interests_str}
- Special Considerations: {job["health_considerations"] or 'None specified'}

LESSON DETAILS:
- Subject: {job["subject"]}
- Topic: {job["topic"]}

YOUR TASK:
Generate content that:
1. Connects the topic to the student's interests to increase engagement
2. Uses appropriate examples related to their interests
3. Adapts explanations considering any health/special considerations
4. Creates assessment questions that are accessible and engaging

OUTPUT FORMAT (JSON):
{{
    "notes_html": "<h2>Topic Title</h2><p>Engaging introduction connecting to student's interests...</p><h3>Key Concepts</h3>...",
    "teacher_instructions": "Detailed instructions for the teacher on how to handle this lesson considering the student's special needs...",
    "mcq_questions": [
        {{
            "question": "...",
            "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
            "correct_answer": "A",
            "explanation": "..."
        }}
    ],
    "essay_questions": [
        {{
            "question": "...",
            "marks": 10,
            "key_points": ["point1", "point2", "point3"]
        }}
    ]
}}

CONTENT GUIDELINES:
1. Make the notes engaging by relating concepts to {interests_str}
2. Use clear, simple language appropriate for {job["edu_lvl"] or 'secondary'} level
3. Include practical examples and analogies
4. For teacher instructions, provide:
   - Specific strategies for the student's considerations
   - Timing suggestions
   - Alternative approaches if needed
   - Signs to watch for
5. Create 5 MCQ questions and 2 essay questions
6. NO emojis in any content
7. Use HTML formatting for notes (h2, h3, p, ul, li, strong)

Generate the JSON now:"""

        # Call Vertex AI
        response = _ai_model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 8192,
            }
        )
        
        response_text = response.text.strip()
        
        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # Parse JSON
        content = json.loads(response_text)
        
        logger.info(f"[Worker {self.worker_id}] Generated {len(content.get('notes_html', ''))} chars of notes")
        
        # Generate images
        images = await self._generate_images(job, pack_id)
        
        # Build the structured pack
        pack_json = self._build_pack_slides(job, content, images)
        
        # Save to database
        await self._save_pack_content(
            pack_id=pack_id,
            content_json=pack_json,
            teacher_instructions=content.get("teacher_instructions", ""),
            status="completed"
        )
        
        return True
    
    async def _generate_images(self, job: Dict, pack_id: str) -> List[Dict]:
        """Generate images for the pack."""
        from app.slide_builder.image_generator import generate_image_with_vertex, upload_image_to_gcs
        
        images = []
        topic = job["topic"]
        subject = job["subject"]
        
        image_prompts = [
            f"Educational diagram explaining {topic} in {subject}, clean simple illustration",
            f"Visual representation of key concepts in {topic}, educational style, clear labels using icons only",
            f"Engaging illustration connecting {topic} to everyday life, student-friendly, colorful"
        ]
        
        for i, prompt in enumerate(image_prompts):
            try:
                logger.info(f"[Worker {self.worker_id}] Generating image {i+1}/3...")
                image_bytes = await generate_image_with_vertex(prompt)
                
                if image_bytes:
                    gcs_path = f"student_support/{pack_id}/image_{i+1}.png"
                    public_url, saved_path = await upload_image_to_gcs(image_bytes, gcs_path)
                    
                    images.append({
                        "gcs_path": saved_path,
                        "alt_text": f"Illustration {i+1} for {topic}",
                        "caption": f"Visual aid for understanding {topic}"
                    })
                    logger.info(f"[Worker {self.worker_id}] Uploaded image {i+1}")
                    
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Error generating image {i+1}: {e}")
        
        return images
    
    def _build_pack_slides(self, job: Dict, content: Dict, images: List[Dict]) -> Dict:
        """Build the structured pack JSON."""
        from uuid import uuid4
        
        slides = []
        slide_num = 1
        
        student_name = job["student_name"]
        subject = job["subject"]
        class_name = job["class_name"]
        topic = job["topic"]
        interests = job["interests"]
        
        # Title slide
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "title",
            "layout": "title_center",
            "content": {
                "title": f"Personalized Learning Pack: {topic}",
                "subtitle": f"Prepared for {student_name} - {subject} ({class_name})"
            }
        })
        slide_num += 1
        
        # Profile slide
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "profile",
            "layout": "text_only",
            "content": {
                "title": "About This Pack",
                "html_content": f"""
                    <p>This learning pack has been specially designed for <strong>{student_name}</strong>.</p>
                    <p>It connects the topic of <strong>{topic}</strong> to your interests: <strong>{', '.join(interests) if interests else 'general learning'}</strong>.</p>
                """
            }
        })
        slide_num += 1
        
        # Visual gallery
        if images:
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "visual_gallery",
                "layout": "image_grid",
                "content": {
                    "title": "Visual Learning Aids",
                    "description": "These diagrams will help you understand the key concepts.",
                    "images": images
                }
            })
            slide_num += 1
        
        # Notes slide
        if content.get("notes_html"):
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "notes",
                "layout": "notes",
                "content": {
                    "title": "Your Learning Notes",
                    "html_content": content["notes_html"]
                }
            })
            slide_num += 1
        
        # Teacher instructions slide
        if content.get("teacher_instructions"):
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "teacher_notes",
                "layout": "notes",
                "content": {
                    "title": "Teacher Instructions",
                    "description": "Special guidance for teaching this topic to this student",
                    "html_content": f"<div class='teacher-only'>{content['teacher_instructions']}</div>"
                }
            })
            slide_num += 1
        
        # MCQ assessment
        mcq_questions = content.get("mcq_questions", [])
        if mcq_questions:
            questions_only = []
            for i, q in enumerate(mcq_questions):
                questions_only.append({
                    "question_number": i + 1,
                    "question": q.get("question", ""),
                    "options": [{"label": chr(65+j), "text": opt.replace(f"{chr(65+j)}) ", "").replace(f"{chr(65+j)}. ", "")} 
                               for j, opt in enumerate(q.get("options", []))]
                })
            
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "assessment_mcq",
                "layout": "assessment",
                "content": {
                    "title": "Check Your Understanding",
                    "instructions": "Choose the best answer for each question.",
                    "questions": questions_only
                }
            })
            slide_num += 1
            
            # MCQ answer key
            mcq_answers = []
            for i, q in enumerate(mcq_questions):
                mcq_answers.append({
                    "question_number": i + 1,
                    "question": q.get("question", "")[:100] + "...",
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", "")
                })
            
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "answer_key_mcq",
                "layout": "answer_key",
                "content": {
                    "title": "Answer Key - Multiple Choice",
                    "note": "Check your answers below.",
                    "answers": mcq_answers
                }
            })
            slide_num += 1
        
        # Essay questions
        essay_questions = content.get("essay_questions", [])
        if essay_questions:
            essay_q = []
            for i, q in enumerate(essay_questions):
                essay_q.append({
                    "question_number": i + 1,
                    "question": q.get("question", ""),
                    "marks": q.get("marks", 10)
                })
            
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "assessment_essay",
                "layout": "assessment",
                "content": {
                    "title": "Think and Write",
                    "instructions": "Answer these questions in your own words.",
                    "questions": essay_q
                }
            })
            slide_num += 1
            
            # Essay answer key
            essay_answers = []
            for i, q in enumerate(essay_questions):
                essay_answers.append({
                    "question_number": i + 1,
                    "question": q.get("question", "")[:100] + "...",
                    "key_points": q.get("key_points", []),
                    "marks": q.get("marks", 10)
                })
            
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "answer_key_essay",
                "layout": "answer_key",
                "content": {
                    "title": "Answer Key - Essay Questions",
                    "note": "Your answers should include these key points.",
                    "answers": essay_answers
                }
            })
            slide_num += 1
        
        return {
            "pack_id": str(uuid4()),
            "student_name": student_name,
            "subject": subject,
            "class_level": class_name,
            "topic": topic,
            "interests": interests,
            "generated_at": datetime.utcnow().isoformat(),
            "slides": slides,
            "summary": {
                "total_slides": len(slides),
                "has_notes": bool(content.get("notes_html")),
                "image_count": len(images),
                "has_teacher_instructions": bool(content.get("teacher_instructions")),
                "mcq_count": len(mcq_questions),
                "essay_count": len(essay_questions)
            }
        }
    
    async def _save_pack_content(self, pack_id: str, content_json: Dict, teacher_instructions: str, status: str):
        """Save the generated pack content to database."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import async_engine
        
        async with AsyncSession(async_engine) as db:
            try:
                await db.execute(
                    text("""
                        UPDATE student_support_packs 
                        SET content_json = CAST(:content AS jsonb),
                            teacher_instructions = :instructions,
                            status = :status,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = CAST(:pack_id AS uuid)
                    """),
                    {
                        "pack_id": pack_id,
                        "content": json.dumps(content_json),
                        "instructions": teacher_instructions,
                        "status": status
                    }
                )
                await db.commit()
                logger.info(f"[Worker {self.worker_id}] Saved pack content for {pack_id}")
            except Exception as e:
                logger.error(f"[Worker {self.worker_id}] Failed to save pack content: {e}")
                raise
    
    async def _mark_job_failed(self, pack_id: str, error: str):
        """Mark a job as failed in the database."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.database import async_engine
        
        async with AsyncSession(async_engine) as db:
            await db.execute(
                text("""
                    UPDATE student_support_packs 
                    SET status = 'failed',
                        teacher_instructions = :error,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = CAST(:pack_id AS uuid)
                """),
                {"pack_id": pack_id, "error": f"Generation failed: {error}"}
            )
            await db.commit()
            logger.warning(f"[Worker {self.worker_id}] Marked job {pack_id} as failed")


async def _ensure_ai_initialized():
    """Initialize the AI model if not already done."""
    global _ai_model, _ai_initialized
    
    if _ai_initialized and _ai_model:
        return
    
    logger.info("[AI] Initializing Vertex AI model...")
    
    import vertexai
    from vertexai.generative_models import GenerativeModel
    
    # Load credentials
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
    
    _ai_model = GenerativeModel("gemini-2.0-flash-exp")
    _ai_initialized = True
    
    logger.info("[AI] Vertex AI model initialized successfully")


async def start_workers():
    """Start the background worker pool."""
    global _workers_running, _worker_tasks
    
    if _workers_running:
        logger.warning("[Workers] Workers already running")
        return
    
    logger.info(f"[Workers] Starting {NUM_WORKERS} workers...")
    
    # Initialize AI before starting workers
    await _ensure_ai_initialized()
    
    _workers_running = True
    
    for i in range(NUM_WORKERS):
        worker = StudentSupportWorker(worker_id=i + 1)
        task = asyncio.create_task(worker.start())
        _worker_tasks.append((worker, task))
    
    logger.info(f"[Workers] {NUM_WORKERS} workers started")


async def stop_workers():
    """Stop all background workers gracefully."""
    global _workers_running, _worker_tasks
    
    if not _workers_running:
        return
    
    logger.info("[Workers] Stopping workers...")
    
    _workers_running = False
    
    for worker, task in _worker_tasks:
        worker.stop()
    
    # Wait for workers to finish current jobs
    for worker, task in _worker_tasks:
        try:
            await asyncio.wait_for(task, timeout=30)
        except asyncio.TimeoutError:
            task.cancel()
    
    _worker_tasks.clear()
    logger.info("[Workers] All workers stopped")


# CLI entry point
if __name__ == "__main__":
    import sys
    
    async def main():
        print("=" * 60)
        print("Student Support Worker Service")
        print("=" * 60)
        print(f"Workers: {NUM_WORKERS}")
        print(f"Max Retries: {MAX_RETRIES}")
        print(f"Poll Interval: {POLL_INTERVAL}s")
        print("=" * 60)
        
        await start_workers()
        
        try:
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n[Shutdown] Received interrupt signal")
        finally:
            await stop_workers()
            print("[Shutdown] Complete")
    
    asyncio.run(main())
