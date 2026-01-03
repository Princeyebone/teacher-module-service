"""
Student Support Pack Generator

Generates personalized lesson packs for students with specific needs,
interests, and health considerations. Includes:
- Personalized notes tailored to student's interests
- Visual aids (images)
- Teacher instructions for handling special considerations
- Assessment questions adapted to the student's needs
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from database import get_db
from config import settings

# Set up logging
logger = logging.getLogger("student_support")
logger.setLevel(logging.INFO)

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 2.0


async def generate_student_support_pack(
    pack_id: str,
    teacher_id: str,
    student_name: str,
    subject: str,
    class_name: str,
    topic: str,
    interests: List[str],
    health_considerations: str,
    edu_sys: Optional[str] = None,
    edu_lvl: Optional[str] = None
) -> bool:
    """
    Main entry point to generate a personalized student support pack.
    
    This creates a lesson pack specifically tailored to a student's:
    - Learning interests (to make content engaging)
    - Health/special considerations (to adapt delivery)
    - Education level (to match appropriate complexity)
    
    The pack includes:
    1. Personalized notes connecting topic to student's interests
    2. Visual aids (images)
    3. Teacher instructions for handling special considerations
    4. Adapted assessment questions
    """
    logger.info(f"[START] Student Support Pack for {student_name} - {topic}")
    
    try:
        # Update status to processing
        await _update_pack_status(pack_id, "processing")
        
        # Generate personalized content using AI
        content = await _generate_personalized_content(
            student_name=student_name,
            subject=subject,
            class_name=class_name,
            topic=topic,
            interests=interests,
            health_considerations=health_considerations,
            edu_sys=edu_sys,
            edu_lvl=edu_lvl
        )
        
        if not content:
            logger.error(f"[ERROR] Failed to generate content for {student_name}")
            await _update_pack_status(pack_id, "failed")
            return False
        
        # Generate images for the content with educational context
        images = await _generate_support_images(
            topic=topic,
            subject=subject,
            interests=interests,
            pack_id=pack_id,
            class_name=class_name,
            edu_lvl=edu_lvl,
            edu_sys=edu_sys
        )
        
        # Build the structured pack
        pack_json = _build_support_pack_slides(
            student_name=student_name,
            subject=subject,
            class_name=class_name,
            topic=topic,
            interests=interests,
            notes_html=content.get("notes_html", ""),
            teacher_instructions=content.get("teacher_instructions", ""),
            images=images,
            mcq_questions=content.get("mcq_questions", []),
            essay_questions=content.get("essay_questions", [])
        )
        
        # Save to database
        await _save_pack_content(
            pack_id=pack_id,
            content_json=pack_json,
            teacher_instructions=content.get("teacher_instructions", ""),
            status="completed"
        )
        
        logger.info(f"[SUCCESS] Student Support Pack completed for {student_name}")
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Student Support Pack failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await _update_pack_status(pack_id, "failed")
        return False


async def _generate_personalized_content(
    student_name: str,
    subject: str,
    class_name: str,
    topic: str,
    interests: List[str],
    health_considerations: str,
    edu_sys: Optional[str],
    edu_lvl: Optional[str]
) -> Optional[Dict]:
    """Generate personalized content using AI."""
    
    interests_str = ", ".join(interests) if interests else "general learning"
    
    prompt = f"""You are a friendly teacher creating personalized lesson content for a student.

STUDENT PROFILE:
- Name: {student_name}
- Class Level: {class_name}
- Education Level: {edu_lvl or 'Secondary'}
- Interests: {interests_str}
- Special Considerations: {health_considerations or 'None specified'}

CRITICAL - READ CAREFULLY:
You MUST teach ONLY about this specific topic: "{topic}"

DO NOT teach about "{subject}" in general.
DO NOT teach about other topics.
ONLY teach about: "{topic}"

For example:
- If topic is "Fractions", teach about fractions (parts of a whole), NOT friction (physics force)
- If topic is "Photosynthesis", teach about photosynthesis, NOT general biology
- If topic is "World War 2", teach about WW2, NOT general history

YOUR TASK:
Create comprehensive teaching content that explains "{topic}" in a way that:
1. Connects to the student's interests ({interests_str})
2. Uses simple, engaging language
3. Considers their special needs
4. Provides clear examples and practice

MANDATORY STRUCTURE - YOU MUST FOLLOW THIS EXACTLY:

For EACH major concept within "{topic}", you MUST include these sections in this order:

1. Main Idea
2. Step-by-Step Explanation  
3. Everyday Example
4. Common Mistake
5. Practice Questions
6. Answers

CRITICAL FORMATTING RULES:
1. NO EMOJIS - Absolutely no emoji characters
2. Use UNIVERSALLY RELATABLE examples (water, cooking, running, animals, sun, rain, markets, family)
3. Connect examples to student's interests ({interests_str}) when appropriate
4. Be encouraging and supportive
5. Use simple vocabulary appropriate for {edu_lvl or 'secondary'} level
6. Consider special needs: {health_considerations or 'None'}

OUTPUT JSON STRUCTURE:
{{
    "notes_html": "HTML content following the EXACT structure below",
    "teacher_instructions": "Detailed instructions for the teacher on how to handle this lesson considering the student's special needs, timing suggestions, alternative approaches, and signs to watch for",
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

HTML STRUCTURE FOR notes_html - FOLLOW THIS EXACTLY:

<h2>Understanding [First Concept about {topic}]</h2>

<h3>Main Idea</h3>
<p>[One clear sentence explaining this concept]</p>

<h3>Step-by-Step Explanation</h3>
<p>Let me explain this step by step...</p>
<ul>
<li><strong>First:</strong> [Step 1 explanation]</li>
<li><strong>Second:</strong> [Step 2 explanation]</li>
<li><strong>Third:</strong> [Step 3 explanation]</li>
</ul>

<h3>Everyday Example</h3>
<p>[Relatable example connected to {interests_str} if possible]</p>

<h3>Common Mistake</h3>
<p>Many students think that... but actually...</p>

<h3>Practice Questions</h3>
<ul>
<li>Question 1: [Question text]</li>
<li>Question 2: [Question text]</li>
</ul>

<h3>Answers</h3>
<ul>
<li>Answer 1: [Answer text]</li>
<li>Answer 2: [Answer text]</li>
</ul>

<h2>Understanding [Second Concept about {topic}]</h2>

<h3>Main Idea</h3>
<p>[One clear sentence]</p>

<h3>Step-by-Step Explanation</h3>
<p>Let me explain this step by step...</p>
<ul>
<li><strong>First:</strong> [Step 1]</li>
<li><strong>Second:</strong> [Step 2]</li>
<li><strong>Third:</strong> [Step 3]</li>
</ul>

<h3>Everyday Example</h3>
<p>[Relatable example]</p>

<h3>Common Mistake</h3>
<p>Many students think that... but actually...</p>

<h3>Practice Questions</h3>
<ul>
<li>Question 1: [Question text]</li>
<li>Question 2: [Question text]</li>
</ul>

<h3>Answers</h3>
<ul>
<li>Answer 1: [Answer text]</li>
<li>Answer 2: [Answer text]</li>
</ul>

[Continue this EXACT pattern for ALL major concepts about {topic}...]

<h2>Did You Know?</h2>
<p>Here's an amazing fact about {topic}...</p>

ASSESSMENT QUESTIONS:
- Create 5 MCQ questions testing understanding of {topic}
- Create 2 essay questions for deeper thinking about {topic}
- Make questions accessible and engaging

REMEMBER: You are teaching about "{topic}" ONLY. Do not deviate from this topic.

Generate the complete JSON now:"""

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
        
        logger.info("[AI] Generating personalized content...")
        
        response = model.generate_content(
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
        logger.info(f"[AI] Generated {len(content.get('notes_html', ''))} chars of notes")
        
        return content
        
    except json.JSONDecodeError as e:
        logger.error(f"[AI] Failed to parse JSON response: {e}")
        return None
    except Exception as e:
        logger.error(f"[AI] Content generation failed: {e}")
        return None


async def _generate_support_images(
    topic: str,
    subject: str,
    interests: List[str],
    pack_id: str,
    class_name: str = None,
    edu_lvl: str = None,
    edu_sys: str = None
) -> List[Dict]:
    """Generate images relevant to the topic and student interests."""
    # Import the image generator from the main slide builder
    from slide_builder.image_generator import generate_image_with_vertex, upload_image_to_gcs
    
    images = []
    interests_str = ", ".join(interests[:2]) if interests else ""
    
    # Build context for image prompts
    context_parts = []
    if edu_lvl:
        context_parts.append(f"for {edu_lvl} level")
    if class_name:
        context_parts.append(f"{class_name} students")
    context = " ".join(context_parts) if context_parts else "educational"
    
    # Generate 3 images for the support pack with educational context
    image_prompts = [
        f"Educational diagram explaining {topic} {context}, clean simple illustration, clear visual learning aid",
        f"Visual representation of key concepts in {topic} suitable for {class_name or 'students'}, educational style, clear labels using icons only",
        f"Engaging illustration connecting {topic} to everyday life, student-friendly, colorful, appropriate for {edu_lvl or 'secondary'} level"
    ]
    
    # Process images with delays to avoid rate limiting
    DELAY_BETWEEN_IMAGES = 5  # 5 seconds between images
    
    for i, prompt in enumerate(image_prompts):
        try:
            # Add delay between images (except for the first one)
            if i > 0:
                logger.info(f"[IMAGE] Waiting {DELAY_BETWEEN_IMAGES}s before next image to avoid rate limiting...")
                await asyncio.sleep(DELAY_BETWEEN_IMAGES)
            
            logger.info(f"[IMAGE] Generating image {i+1}/3...")
            image_bytes = await generate_image_with_vertex(prompt)
            
            if image_bytes:
                # Upload to GCS with new signature (slide_id, slide_item_id)
                slide_item_id = f"support_image_{i+1}"
                gcs_path = upload_image_to_gcs(image_bytes, pack_id, slide_item_id)
                
                if gcs_path:
                    images.append({
                        "gcs_path": gcs_path,
                        "alt_text": f"Illustration {i+1} for {topic}",
                        "caption": f"Visual aid for understanding {topic}"
                    })
                    logger.info(f"[IMAGE] Uploaded image {i+1} to {gcs_path}")
                else:
                    logger.warning(f"[IMAGE] Failed to upload image {i+1}")
            else:
                logger.warning(f"[IMAGE] Failed to generate image {i+1}")
                
        except Exception as e:
            logger.error(f"[IMAGE] Error generating image {i+1}: {e}")
    
    return images


def _parse_notes_into_slides(html_content: str, start_slide_num: int = 1) -> List[Dict]:
    """
    Parse HTML notes into multiple structured slides.
    Extracts plain text from HTML and structures it like student lesson pack.
    """
    from bs4 import BeautifulSoup
    import copy
    
    slides = []
    slide_num = start_slide_num
    
    # Configuration
    MAX_PARAGRAPHS_PER_SLIDE = 3
    MAX_BULLETS_PER_SLIDE = 6
    MAX_SUBSECTIONS_PER_SLIDE = 2
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all h2 sections (main concepts)
        h2_elements = soup.find_all('h2')
        
        if not h2_elements:
            # Fallback to single slide
            slides.append({
                "id": f"slide-{slide_num}",
                "type": "notes_section",
                "layout": "text_only",
                "content": {
                    "title": "Learning Notes",
                    "content_parts": [{"type": "paragraph", "text": soup.get_text(strip=True)}]
                }
            })
            return slides
        
        # Process each h2 section
        for h2 in h2_elements:
            section_title = h2.get_text(strip=True)
            
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
                
                slide_content_obj = {
                    "title": f"{section_title} (Part {part_num})" if part_num and part_num > 1 else section_title,
                    "content_parts": copy.deepcopy(current_slide_content["content_parts"])
                }
                
                if current_slide_content["paragraphs"]:
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
                
                # Reset
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
                    # Subsections
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
                    
                    if len(current_slide_content["subsections"]) >= MAX_SUBSECTIONS_PER_SLIDE:
                        commit_current_slide(part_counter)
                        part_counter += 1
                    
                    current = sub_current
                    continue
                
                elif current.name == 'p':
                    text = current.get_text(strip=True)
                    if text:
                        if paragraph_count >= MAX_PARAGRAPHS_PER_SLIDE and bullet_count > 0:
                            should_break_slide = True
                        elif paragraph_count >= MAX_PARAGRAPHS_PER_SLIDE * 2:
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
                
                current = current.find_next_sibling()
            
            # Commit whatever is left
            commit_current_slide(part_counter)
        
        logger.info(f"[NOTES-PARSER] Created {len(slides)} slides from HTML notes")
        return slides
        
    except Exception as e:
        logger.error(f"[NOTES-PARSER] Error parsing HTML: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Fallback
        return [{
            "id": f"slide-{start_slide_num}",
            "type": "notes_section",
            "layout": "text_only",
            "content": {
                "title": "Learning Notes",
                "content_parts": [{"type": "paragraph", "text": "Error parsing notes"}]
            }
        }]


def _build_support_pack_slides(
    student_name: str,
    subject: str,
    class_name: str,
    topic: str,
    interests: List[str],
    notes_html: str,
    teacher_instructions: str,
    images: List[Dict],
    mcq_questions: List[Dict],
    essay_questions: List[Dict]
) -> Dict:
    """Build the structured slide-format support pack."""
    
    slides = []
    slide_num = 1
    
    # === 1. Title Slide ===
    slides.append({
        "id": f"slide-{slide_num}",
        "type": "title",
        "layout": "title_center",
        "content": {
            "title": f"Personalized Learning Pack: {topic}",
            "subtitle": f"Prepared for {student_name} ({class_name})"
        }
    })
    slide_num += 1
    
    # === 2. Student Profile Slide ===
    slides.append({
        "id": f"slide-{slide_num}",
        "type": "profile",
        "layout": "text_only",
        "content": {
            "title": "About This Pack",
            "html_content": f"""
                <p>This learning pack has been specially designed for <strong>{student_name}</strong>.</p>
                <p>It connects the topic of <strong>{topic}</strong> to your interests: <strong>{', '.join(interests) if interests else 'general learning'}</strong>.</p>
                <p>Take your time with each section and don't hesitate to ask your teacher for help!</p>
            """
        }
    })
    slide_num += 1
    
    # === 3. Visual Gallery (if images available) ===
    if images:
        image_items = []
        for img in images:
            image_items.append({
                "gcs_path": img.get("gcs_path"),
                "alt_text": img.get("alt_text", "Educational diagram"),
                "caption": img.get("caption", "Visual aid")
            })
        
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "visual_gallery",
            "layout": "image_grid",
            "content": {
                "title": "Visual Learning Aids",
                "description": "These diagrams will help you understand the key concepts.",
                "images": image_items
            }
        })
        slide_num += 1
    
    # === 4. Notes Slides (parsed into structured slides) ===
    if notes_html:
        # Parse HTML into structured slides like student lesson pack
        notes_slides = _parse_notes_into_slides(notes_html, slide_num)
        slides.extend(notes_slides)
        slide_num += len(notes_slides)
    
    # === 5. Teacher Instructions Slide ===
    if teacher_instructions:
        slides.append({
            "id": f"slide-{slide_num}",
            "type": "teacher_notes",
            "layout": "notes",
            "content": {
                "title": "Teacher Instructions",
                "description": "Special guidance for teaching this topic to this student",
                "html_content": f"<div class='teacher-only'>{teacher_instructions}</div>"
            }
        })
        slide_num += 1
    
    # === 6. MCQ Assessment ===
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
    
    # === 7. Essay Questions ===
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
    
    # === 8. MCQ Answer Key ===
    if mcq_questions:
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
    
    # === 9. Essay Answer Key ===
    if essay_questions:
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
            "has_notes": bool(notes_html),
            "image_count": len(images),
            "has_teacher_instructions": bool(teacher_instructions),
            "mcq_count": len(mcq_questions),
            "essay_count": len(essay_questions)
        }
    }


async def _update_pack_status(pack_id: str, status: str):
    """Update the status of a support pack."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from database import async_engine
    
    async with AsyncSession(async_engine) as db:
        await db.execute(
            text("""
                UPDATE student_support_packs 
                SET status = :status, updated_at = CURRENT_TIMESTAMP
                WHERE id = CAST(:pack_id AS uuid)
            """),
            {"pack_id": pack_id, "status": status}
        )
        await db.commit()


async def _save_pack_content(pack_id: str, content_json: Dict, teacher_instructions: str, status: str):
    """Save the generated pack content to database."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from database import async_engine
    
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
            logger.info(f"[DB] Saved pack content for {pack_id}")
        except Exception as e:
            logger.error(f"[DB] Failed to save pack content: {e}")
            raise
