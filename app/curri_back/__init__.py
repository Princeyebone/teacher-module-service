"""
Curriculum Background Processing Package

This package provides a unified background processing pipeline for curriculum files.
It combines:
- Text extraction and chunking
- Embedding generation  
- Retrieval from syllabus knowledge base
- AI prompt building and processing
- Storage in Strand/Substrand/ContentStandard/Indicator tables

Usage:
    # Import the enqueue function
    from app.curri_back.enqueue_curri import enqueue_curriculum_processing, check_strands_exist
    
    # Check if processing is needed
    strands_exist = await check_strands_exist(teacher_id, subject, class_name)
    
    if not strands_exist:
        # Enqueue for immediate processing
        job = await enqueue_curriculum_processing(
            teacher_id=teacher_id,
            gcs_file_name=gcs_file_name,
            subject=subject,
            class_name=class_name,
            session_data=session_data,
            knowledge_id=knowledge_id
        )
    
    # Start the workers
    # python curri_back/run_curri_workers.py start 2
"""

from app.curri_back.enqueue_curri import enqueue_curriculum_processing, check_strands_exist

__all__ = [
    'enqueue_curriculum_processing',
    'check_strands_exist'
]
