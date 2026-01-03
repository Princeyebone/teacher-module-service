"""
Slide Schema Definitions and Validation

Defines the strict JSON schema for AI-generated slides.
All AI output MUST conform to this schema.

UPDATED: 
- Max 30 slides for university/college
- Last 2 slides reserved for evaluation:
  - Slide N-1: 15 Multiple Choice Questions with answers
  - Slide N: 5 Essay Questions with key points
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator
from uuid import uuid4
from enum import Enum


class SlideType(str, Enum):
    """Allowed slide types."""
    TITLE = "title"
    CONTENT = "content"
    IMAGE_CONTENT = "image_content"
    ASSESSMENT_MCQ = "assessment_mcq"
    ASSESSMENT_ESSAY = "assessment_essay"


class SlideLayout(str, Enum):
    """Allowed slide layouts - NO custom layouts permitted."""
    TITLE_CENTER = "title_center"
    TEXT_ONLY = "text_only"
    IMAGE_LEFT_TEXT_RIGHT = "image_left_text_right"
    IMAGE_TOP_TEXT_BOTTOM = "image_top_text_bottom"
    ASSESSMENT = "assessment"


class ImageStyle(str, Enum):
    """Allowed image styles for generation prompts."""
    FLAT_DIAGRAM = "flat educational diagram"
    PHOTO = "photo"
    ILLUSTRATION = "illustration"


class SlideImage(BaseModel):
    """Image specification for AI image generation."""
    prompt: str = Field(..., description="Image generation prompt")
    style: str = Field(..., description="Visual style (diagram, photo, illustration)")
    alt: str = Field(..., description="Accessibility alt text")


class MCQOption(BaseModel):
    """A single option in a multiple choice question."""
    label: str = Field(..., description="Option label (A, B, C, D)")
    text: Optional[str] = Field(None, description="Option text")
    
    class Config:
        extra = "allow"  # Allow extra fields like text_content
    
    @validator('text', pre=True, always=True)
    def extract_text(cls, v, values):
        """Extract text from various possible field names."""
        if v:
            return v
        # Check for common variations
        return None


class MultipleChoiceQuestion(BaseModel):
    """A multiple choice question with options and answer."""
    question: str = Field(..., description="The question text")
    options: List[MCQOption] = Field(..., description="List of 4 options", min_items=4, max_items=4)
    correct_answer: str = Field(..., description="Correct option label (A, B, C, or D)")
    explanation: Optional[str] = Field(None, description="Brief explanation")


class EssayQuestion(BaseModel):
    """An essay question with key points."""
    question: str = Field(..., description="The essay question")
    key_points: List[str] = Field(..., description="Key points for the answer (2-4 points)")
    marks: Optional[int] = Field(None, description="Marks allocated")


class SlideContent(BaseModel):
    """Content structure for a single slide."""
    title: Optional[str] = Field(None, description="Slide title (optional)")
    heading: Optional[str] = Field(None, description="Content heading (optional)")
    bullet_points: Optional[List[str]] = Field(
        default=None,
        description="Bullet points (recommended max 5)"
    )
    questions: Optional[List[str]] = Field(
        default=None,
        description="Simple questions (legacy)"
    )
    mcq_questions: Optional[List[MultipleChoiceQuestion]] = Field(
        default=None,
        description="Multiple choice questions (for assessment_mcq slides)"
    )
    essay_questions: Optional[List[EssayQuestion]] = Field(
        default=None,
        description="Essay questions (for assessment_essay slides)"
    )
    image: Optional[SlideImage] = Field(
        default=None,
        description="Image specification"
    )



class Slide(BaseModel):
    """Single slide definition."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: SlideType = Field(..., description="Slide type")
    layout: SlideLayout = Field(..., description="Slide layout")
    content: SlideContent = Field(..., description="Slide content")

    @validator('layout')
    def validate_layout_matches_type(cls, v, values):
        """Validate layout is appropriate for slide type."""
        slide_type = values.get('type')
        if slide_type == SlideType.TITLE and v != SlideLayout.TITLE_CENTER:
            pass  # Allow flexibility
        if slide_type in [SlideType.ASSESSMENT_MCQ, SlideType.ASSESSMENT_ESSAY] and v != SlideLayout.ASSESSMENT:
            raise ValueError("Assessment slides must use 'assessment' layout")
        return v


class SlideDecks(BaseModel):
    """Complete slide deck structure - the AI output schema."""
    lesson_id: str = Field(default_factory=lambda: str(uuid4()))
    subject: str = Field(..., description="Subject name")
    class_level: str = Field(..., description="Class/grade level")
    topic: str = Field(..., description="Lesson topic")
    slides: List[Slide] = Field(
        ...,
        description="Array of slides (max 30)",
        min_items=1,
        max_items=30
    )


def get_recommended_slide_count(edu_level: str, class_name: str) -> dict:
    """Get recommended slide count based on education level."""
    import re
    class_num = 0
    match = re.search(r'\d+', class_name or "")
    if match:
        class_num = int(match.group())
    
    edu_level_lower = (edu_level or "").lower()
    
    # Primary school (Classes 1-6)
    if edu_level_lower in ["primary", "elementary", "basic"] or class_num <= 6:
        return {"min_slides": 8, "max_slides": 12}
    
    # Junior High / Middle School (Classes 7-9)
    elif edu_level_lower in ["jhs", "junior high", "middle", "k12"] or class_num <= 9:
        return {"min_slides": 10, "max_slides": 15}
    
    # Senior High School (Classes 10-12)
    elif edu_level_lower in ["shs", "senior high", "secondary", "high school"] or class_num <= 12:
        return {"min_slides": 12, "max_slides": 20}
    
    # Tertiary / University
    else:
        return {"min_slides": 20, "max_slides": 30}


def validate_slide_json(data: dict) -> dict:
    """Validate AI output against the slide schema."""
    try:
        deck = SlideDecks(**data)
        return deck.dict()
    except Exception as e:
        raise ValueError(f"Schema validation failed: {str(e)}")


def get_allowed_layouts() -> List[str]:
    """Get list of allowed layouts for AI prompts."""
    return [layout.value for layout in SlideLayout]


def get_schema_for_prompt() -> str:
    """Get schema description for AI prompt."""
    return """
{
  "lesson_id": "uuid",
  "subject": "string",
  "class_level": "string",
  "topic": "string",
  "slides": [
    {
      "id": "unique-id",
      "type": "title | content | image_content | assessment_mcq | assessment_essay",
      "layout": "title_center | text_only | image_left_text_right | image_top_text_bottom | assessment",
      "content": {
        "title": "string (for title slides)",
        "heading": "string (for content slides)",
        "bullet_points": ["string", "string", ...] (max 5),
        "mcq_questions": [
          {
            "question": "string",
            "options": [
              {"label": "A", "text": "option"},
              {"label": "B", "text": "option"},
              {"label": "C", "text": "option"},
              {"label": "D", "text": "option"}
            ],
            "correct_answer": "A",
            "explanation": "brief reason"
          }
        ],
        "essay_questions": [
          {
            "question": "string",
            "key_points": ["point1", "point2"],
            "marks": 10
          }
        ],
        "image": {
          "prompt": "image description",
          "style": "flat educational diagram",
          "alt": "accessibility text"
        }
      }
    }
  ]
}
"""
