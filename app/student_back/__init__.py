"""
Student Back - Background Worker Module

This module handles background processing for personalized student support packs.
It uses a worker pool pattern with proper retries and AI initialization.
"""

from .student_support_generator import generate_student_support_pack
from .worker import StudentSupportWorker, start_workers, stop_workers

__all__ = [
    'generate_student_support_pack',
    'StudentSupportWorker',
    'start_workers',
    'stop_workers'
]
