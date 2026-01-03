"""
Weekly Lesson Notes Module

This module handles automatic generation of weekly lesson notes for teachers.
Scheduled to run on Wednesday and Thursday at 12 AM - 2 AM local time.

Components:
- note_scheduler.py: APScheduler configuration
- note_processor.py: Main processing logic
- note_prompts.py: AI prompt builders
"""

from .note_processor import run_lesson_note_generation_cycle
from .note_scheduler import start_scheduler, create_scheduler

__all__ = [
    'run_lesson_note_generation_cycle',
    'start_scheduler',
    'create_scheduler'
]
