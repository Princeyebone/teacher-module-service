"""
Lesson Brief Scheduler Package

Automatically generates lesson briefs for teachers around midnight
in their local timezone.
"""

from .brief_processor import run_brief_generation_cycle
from .brief_scheduler import start_scheduler, create_scheduler
from .country_timezone_map import get_timezone_for_country
from .brief_prompts import build_lesson_brief_prompt
from .brief_retrieval import retrieve_lesson_design_chunks, retrieve_chunks_for_lesson

__all__ = [
    'run_brief_generation_cycle',
    'start_scheduler',
    'create_scheduler',
    'get_timezone_for_country',
    'build_lesson_brief_prompt',
    'retrieve_lesson_design_chunks',
    'retrieve_chunks_for_lesson',
]
