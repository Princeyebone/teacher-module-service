"""
Course/Subject Outline Generation Background System

Generates comprehensive course outlines from curriculum data.
"""

from .outline_processor import process_outline_task
from .enqueue_outline import enqueue_outline_generation, get_outline_job_status

__all__ = [
    'process_outline_task',
    'enqueue_outline_generation',
    'get_outline_job_status'
]
