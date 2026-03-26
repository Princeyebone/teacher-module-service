"""
Slide Builder Package

AI-powered lesson slide generation system that runs on a schedule.
Generates structured JSON slides for teachers based on their curriculum.

Features:
- Multi-pillar RAG retrieval (Cognitive, Subject, Lesson Design, Evaluation)
- Timezone-aware scheduling (12 AM - 2 AM window)
- Education context integration (system, level, country)
- Duplicate prevention (one generation per day)
- History preservation
"""

from .slide_processor import run_slide_generation_cycle, process_teacher_slides
from .slide_scheduler import start_scheduler, create_scheduler
from .slide_retrieval import retrieve_all_pillars_for_slides, format_chunks_for_ai_prompt
from .slide_schema import validate_slide_json, SlideDecks, SlideType, SlideLayout

__all__ = [
    'run_slide_generation_cycle',
    'process_teacher_slides',
    'start_scheduler',
    'create_scheduler',
    'retrieve_all_pillars_for_slides',
    'format_chunks_for_ai_prompt',
    'validate_slide_json',
    'SlideDecks',
    'SlideType',
    'SlideLayout',
]
