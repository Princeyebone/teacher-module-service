"""
Slide Prompt Builder

Builds structured prompts for Vertex AI to generate lesson slides.
"""

from typing import Dict, Any, Optional, List
from .slide_schema import get_schema_for_prompt, get_allowed_layouts


def build_slide_generation_prompt(
    subject: str,
    class_level: str,
    topic: str,
    indicator_text: Optional[str] = None,
    content_standard: Optional[str] = None,
    strand_name: Optional[str] = None,
    substrand_name: Optional[str] = None,
    education_level: str = "junior high",
    additional_context: Optional[str] = None
) -> str:
    """
    Build the prompt for Vertex AI slide generation.
    
    Args:
        subject: Subject name (e.g., "Mathematics")
        class_level: Class/grade level (e.g., "Class 7")
        topic: Lesson topic
        indicator_text: Learning indicator text
        content_standard: Content standard text
        strand_name: Curriculum strand
        substrand_name: Curriculum substrand
        education_level: Education level (junior high, senior high, primary)
        additional_context: Any additional context
        
    Returns:
        Formatted prompt string
    """
    
    # Build curriculum context
    curriculum_context = ""
    if strand_name:
        curriculum_context += f"- Strand: {strand_name}\n"
    if substrand_name:
        curriculum_context += f"- Substrand: {substrand_name}\n"
    if content_standard:
        curriculum_context += f"- Content Standard: {content_standard}\n"
    if indicator_text:
        curriculum_context += f"- Learning Indicator: {indicator_text}\n"
    
    if not curriculum_context:
        curriculum_context = "No specific curriculum context provided.\n"
    
    # Get allowed layouts
    layouts = get_allowed_layouts()
    layouts_str = "\n  ".join(layouts)
    
    # Get schema
    schema = get_schema_for_prompt()
    
    prompt = f"""You are an educational content planner specializing in creating engaging lesson slides.

Generate lesson slides as JSON ONLY.
Do not include any explanations, markdown, or text outside the JSON.

STRICT RULES:
1. Use ONLY these layouts:
  {layouts_str}
2. Limit bullet points to 5 per slide maximum
3. YOU MUST include EXACTLY 5 images across all slides - this is mandatory
4. Prefer diagrams for science and math topics
5. Language must be appropriate for {education_level} level students
6. Generate 10-14 slides total
7. Start with a title slide using 'title_center' layout
8. End with an assessment slide if appropriate
9. Do NOT use markdown in any text content
10. Do NOT include extra keys not in the schema
11. Distribute the 5 images across the content slides that explain key concepts

CRITICAL: Every slide deck MUST have exactly 5 images. Failure to include 5 images is unacceptable.

LESSON CONTEXT:
- Subject: {subject}
- Class Level: {class_level}
- Topic: {topic}

CURRICULUM CONTEXT:
{curriculum_context}
{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

REQUIRED JSON SCHEMA:
{schema}

IMAGE PROMPT GUIDELINES:
When including images, write clear, educational prompts:
- For diagrams: "flat educational diagram showing [concept], clean lines, labeled parts"
- For illustrations: "educational illustration of [concept], colorful, student-friendly"
- For photos: "real photograph of [subject], clear, high quality, educational context"

Generate the slides now. Return ONLY the valid JSON object.
"""
    
    return prompt


def build_image_generation_prompt(
    original_prompt: str,
    style: str,
    subject: str,
    topic: str
) -> str:
    """
    Enhance an image prompt for better generation results.
    
    Args:
        original_prompt: The AI-generated image prompt
        style: Image style (flat educational diagram, photo, illustration)
        subject: Subject area
        topic: Lesson topic
        
    Returns:
        Enhanced prompt for image generation
    """
    
    style_modifiers = {
        "flat educational diagram": "clean vector style, simple shapes, labeled parts, educational, clear lines, minimal colors, infographic style",
        "photo": "high quality photograph, realistic, clear, educational context, professional",
        "illustration": "colorful illustration, cartoon style, educational, engaging, student-friendly, vibrant"
    }
    
    modifier = style_modifiers.get(style, "educational, clear, professional")
    
    enhanced_prompt = f"{original_prompt}. Style: {modifier}. Context: {subject} lesson about {topic}. Safe for students."
    
    return enhanced_prompt


def extract_image_prompts_from_slides(slide_deck: Dict[str, Any], max_images: int = 5) -> List[Dict[str, Any]]:
    """
    Extract all image prompts from a slide deck for batch processing.
    
    Args:
        slide_deck: The validated slide deck JSON
        max_images: Maximum number of images to extract (default: 5)
        
    Returns:
        List of image prompt specifications with slide IDs (limited to max_images)
    """
    image_prompts = []
    
    slides = slide_deck.get("slides", [])
    subject = slide_deck.get("subject", "")
    topic = slide_deck.get("topic", "")
    
    for slide in slides:
        # Stop if we've reached the maximum number of images
        if len(image_prompts) >= max_images:
            break
            
        slide_id = slide.get("id")
        content = slide.get("content", {})
        image = content.get("image")
        
        if image:
            image_prompts.append({
                "slide_item_id": slide_id,
                "prompt": image.get("prompt", ""),
                "style": image.get("style", "illustration"),
                "alt": image.get("alt", ""),
                "enhanced_prompt": build_image_generation_prompt(
                    image.get("prompt", ""),
                    image.get("style", "illustration"),
                    subject,
                    topic
                )
            })
    
    return image_prompts
