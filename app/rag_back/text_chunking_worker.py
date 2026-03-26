"""
Background Task for Text Extraction and Chunking using text.py implementation

This module provides background task processing for text extraction and chunking
using the implementation from rag/text.py, which extracts text from PDFs using 
PyMuPDF with OCR fallback and chunks the text using LangChain.

Usage:
    from app.rag_back.text_chunking_worker import process_text_chunking_task
    job_id = await enqueue_text_chunking(teacher_id, file_path, gcs_file_name, knowledge_id, metadata)
"""

import os
import json
import asyncio
import logging
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID

# Initialize logger early
logger = logging.getLogger(__name__)

# ARQ and database imports
from arq import create_pool, ArqRedis
from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
import redis.asyncio as redis

# Project imports
from app.core.config import settings
from app.models.model import KnowledgeMetadata, KnowledgeEmbedding, TestText
from app.core.database import get_db

# Import from sch_ground.background which contains shared utilities
try:
    from app.sch_ground.background import async_engine, publish_ws_message, save_notification
except ImportError:
    # If running as script directly, add parent directory to path
    import sys
    import os
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, parent_dir)
    from app.sch_ground.background import async_engine, publish_ws_message, save_notification

# Import text processing functions from rag_back.text_processing
try:
    from app.rag_back.text_processing import (
        extract_text_from_pdf_pymupdf,
        chunk_text_with_langchain,
        store_chunks_in_testtext_table,
        process_text_chunking_task
    )
except ImportError as e:
    logger.error(f"Failed to import text processing components: {e}")
    raise

# Create separate Redis settings for text chunking tasks
text_chunking_redis_settings = RedisSettings(host="localhost", port=6379, database=0, conn_timeout=10, conn_retries=5, conn_retry_delay=1)

# Initialize async Redis client
redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Text processing functions are imported from rag_back.text_processing

# Worker configurations for two workers
worker_config_1 = {
    'functions': [process_text_chunking_task],
    'redis_settings': text_chunking_redis_settings,
    'queue_name': 'text_chunking_queue_1',
    'max_tries': 3,
    'retry_delay': 30,
    'job_timeout': 600,  # 10 minutes max per job
    'concurrent_jobs': 1,
    'keep_result': 3600,  # Keep job results for 1 hour
    'max_jobs': 50
}

worker_config_2 = {
    'functions': [process_text_chunking_task],
    'redis_settings': text_chunking_redis_settings,
    'queue_name': 'text_chunking_queue_2',
    'max_tries': 3,
    'retry_delay': 30,
    'job_timeout': 600,  # 10 minutes max per job
    'concurrent_jobs': 1,
    'keep_result': 3600,  # Keep job results for 1 hour
    'max_jobs': 50
}