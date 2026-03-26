#!/usr/bin/env python3
"""
Background Task Scheduler for RAG Processing

This module provides a background task that monitors newly created KnowledgeMetadata entries
and schedules RAG processing (text extraction, chunking, and embedding) 120 seconds after upload.

The flow is:
1. User uploads file via curriculum or semester plan upload endpoint
2. KnowledgeMetadata entry is created
3. This background task detects new entries
4. After 120 seconds, it downloads the file from GCS
5. Enqueues the text extraction task (which automatically chains to chunking and embedding)

Usage:
    Run as a separate background process:
    python rag_back/schedule_rag_processing.py
    
    Or with a specific teacher_id to filter entries:
    python rag_back/schedule_rag_processing.py --teacher-id <teacher_uuid>
"""

import asyncio
import logging
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import configuration and utilities
try:
    from app.core.config import settings
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# Import database and models
try:
    # Import from sch_ground.background which contains the database engine and session utilities
    from app.core.database import get_db
    from app.models.model import KnowledgeMetadata
    from sqlalchemy import select
    DATABASE_AVAILABLE = True
except ImportError as e:
    DATABASE_AVAILABLE = False
    print(f"❌ Database imports failed: {e}")

# Import GCS utilities
try:
    # Import from file_handler.rag_file_handler which contains GCS utilities
    from app.services.gcs_utils import get_file_from_gcs
    GCS_AVAILABLE = True
except ImportError as e:
    GCS_AVAILABLE = False
    print(f"❌ GCS imports failed: {e}")

# Import text chunking enqueue function
try:
    from app.rag_back.enqueue_text_chunking import enqueue_text_chunking_task
    ENQUEUE_AVAILABLE = True
except ImportError as e:
    ENQUEUE_AVAILABLE = False
    print(f"❌ Enqueue imports failed: {e}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('rag_scheduler.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Track processed entries to avoid duplicate processing
# This persists across the lifetime of the scheduler process
processed_entries = set()

async def download_file_from_gcs(bucket_name: str, blob_name: str, local_path: str) -> bool:
    """
    Download file from GCS to local storage.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
        local_path: Local path to save the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"📥 Downloading file from GCS: {blob_name}")
        
        # Download file content
        content = get_file_from_gcs(bucket_name, blob_name)
        
        if content is None:
            logger.error(f"❌ Failed to download file from GCS: {blob_name}")
            return False
            
        # Save to local file
        with open(local_path, 'wb') as f:
            f.write(content)
            
        logger.info(f"✅ Successfully downloaded file to: {local_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error downloading file from GCS: {e}")
        return False

async def schedule_rag_processing_for_entry(knowledge_record: KnowledgeMetadata) -> bool:
    """
    Schedule RAG processing for a KnowledgeMetadata entry.
    
    Args:
        knowledge_record: KnowledgeMetadata record to process
        
    Returns:
        True if successfully scheduled, False otherwise
    """
    try:
        knowledge_id = knowledge_record.id
        # Handle NULL teacher_id correctly
        teacher_id = str(knowledge_record.teacher_id) if knowledge_record.teacher_id is not None else None
        file_path = knowledge_record.file_path
        notes = knowledge_record.notes or "Untitled Document"
        
        logger.info(f"🚀 Scheduling RAG processing for KnowledgeMetadata ID: {knowledge_id}")
        logger.info(f"   Teacher ID: {teacher_id}")
        logger.info(f"   File Path: {file_path}")
        logger.info(f"   Notes: {notes}")
        
        if not file_path:
            logger.error(f"❌ No file path found for KnowledgeMetadata ID: {knowledge_id}")
            return False
            
        # Parse GCS URI if it's a full GCS URL
        bucket_name = settings.GCS_BUCKET_NAME
        blob_name = file_path
        
        # Handle gs:// URLs by extracting bucket and blob name
        if file_path.startswith("gs://"):
            # Parse gs://bucket_name/blob_name format
            parts = file_path[5:].split("/", 1)  # Remove "gs://" and split on first "/"
            if len(parts) == 2:
                bucket_name = parts[0]
                blob_name = parts[1]
                logger.info(f"   Parsed GCS URI - Bucket: {bucket_name}, Blob: {blob_name}")
            else:
                logger.warning(f"   Invalid GCS URI format: {file_path}, using as blob name")
        
        # Download file from GCS to local storage
        # Create local directory if it doesn't exist
        local_dir = "./rag_downloads"
        os.makedirs(local_dir, exist_ok=True)
        
        # Generate local file path
        file_extension = os.path.splitext(blob_name)[1] or ".dat"
        local_file_path = os.path.join(local_dir, f"knowledge_{knowledge_id}_{int(time.time())}{file_extension}")
        
        # Download file from GCS
        download_success = await download_file_from_gcs(
            bucket_name, 
            blob_name, 
            local_file_path
        )
        
        if not download_success:
            logger.error(f"❌ Failed to download file for KnowledgeMetadata ID: {knowledge_id}")
            return False
            
        # Prepare metadata for text chunking task
        metadata = {
            "subject": knowledge_record.subject or "Unknown",
            "notes": knowledge_record.notes or "",
            "level": knowledge_record.level or "Unknown",
            "region": knowledge_record.region or "",
            "source_url": knowledge_record.source_url or "",
            "file_path": knowledge_record.file_path or "",
            "pillar": knowledge_record.pillar or "curriculum"
        }
        
        # Enqueue text chunking task
        # This will automatically chain to embedding processing
        job_id = await enqueue_text_chunking_task(
            teacher_id=teacher_id,
            file_path=local_file_path,
            gcs_file_name=blob_name,  # Use the parsed blob name
            knowledge_id=knowledge_id,  # Pass the knowledge_id
            metadata=metadata
        )
        
        if job_id:
            logger.info(f"✅ Text chunking task enqueued successfully for KnowledgeMetadata ID: {knowledge_id}")
            logger.info(f"   Job ID: {job_id}")
            return True
        else:
            logger.error(f"❌ Failed to enqueue text chunking task for KnowledgeMetadata ID: {knowledge_id}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error scheduling RAG processing for KnowledgeMetadata ID {knowledge_record.id}: {e}")
        return False

async def monitor_new_knowledge_entries(teacher_id: Optional[str] = None):
    """
    Monitor for new KnowledgeMetadata entries and schedule RAG processing.
    
    Args:
        teacher_id: Optional teacher ID to filter entries. If None, processes all entries.
    """
    logger.info(f"🔍 Starting KnowledgeMetadata monitoring for RAG processing")
    if teacher_id:
        logger.info(f"   Filtering by teacher ID: {teacher_id}")
    else:
        logger.info("   Processing entries for all teachers")
    
    while True:
        try:
            # Get database session using get_db generator
            db_gen = get_db()
            db = await db_gen.__anext__()
            
            try:
                # Build query based on whether we're filtering by teacher_id
                query = select(KnowledgeMetadata).where(KnowledgeMetadata.is_embedded == False)
                
                if teacher_id:
                    # Filter by specific teacher_id
                    try:
                        uuid_obj = UUID(teacher_id)
                        query = query.where(KnowledgeMetadata.teacher_id == uuid_obj)
                    except ValueError:
                        logger.error(f"❌ Invalid teacher_id format: {teacher_id}")
                        return
                else:
                    # Process all entries regardless of teacher_id (including NULL teacher_id)
                    pass
                    
                # Order by creation time
                query = query.order_by(KnowledgeMetadata.created_at.desc())
                
                # Execute query
                result = await db.execute(query)
                records = result.scalars().all()
                
                if teacher_id:
                    logger.info(f"📊 Found {len(records)} unembedded KnowledgeMetadata entries for teacher {teacher_id}")
                else:
                    logger.info(f"📊 Found {len(records)} unembedded KnowledgeMetadata entries to check")
                
                for record in records:
                    knowledge_id = record.id
                    
                    # Skip if already processed in this session
                    if knowledge_id in processed_entries:
                        logger.info(f"⏭️ Skipping KnowledgeMetadata ID: {knowledge_id} (already processed)")
                        continue
                        
                    # Check if it's time to process (120 seconds after creation)
                    time_since_creation = datetime.utcnow() - record.created_at
                    if time_since_creation.total_seconds() >= 120:
                        logger.info(f"⏰ Ready to process KnowledgeMetadata ID: {knowledge_id} (created {time_since_creation.total_seconds():.0f}s ago)")
                        
                        # Schedule RAG processing
                        success = await schedule_rag_processing_for_entry(record)
                        
                        if success:
                            # Mark as processed to avoid duplicate processing
                            processed_entries.add(knowledge_id)
                            logger.info(f"✅ Successfully scheduled RAG processing for KnowledgeMetadata ID: {knowledge_id}")
                        else:
                            logger.error(f"❌ Failed to schedule RAG processing for KnowledgeMetadata ID: {knowledge_id}")
                    else:
                        remaining_time = 120 - time_since_creation.total_seconds()
                        logger.info(f"⏳ Waiting for KnowledgeMetadata ID: {knowledge_id} ({remaining_time:.0f}s remaining)")
                        
            except Exception as e:
                logger.error(f"❌ Error monitoring KnowledgeMetadata entries: {e}")
            finally:
                await db_gen.aclose()
                
            # Wait before next check
            await asyncio.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"❌ Critical error in monitoring loop: {e}")
            await asyncio.sleep(60)  # Wait longer on critical errors

def main():
    """Main function to run the RAG processing scheduler"""
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='RAG Processing Scheduler')
        parser.add_argument('--teacher-id', type=str, help='Filter by specific teacher ID')
        args = parser.parse_args()
        
        logger.info("[STARTING] RAG Processing Scheduler...")
        if args.teacher_id:
            logger.info(f"   Teacher ID filter: {args.teacher_id}")
        
        # Check prerequisites
        if not CONFIG_AVAILABLE:
            logger.error("❌ Configuration not available")
            return
            
        if not DATABASE_AVAILABLE:
            logger.error("❌ Database components not available")
            return
            
        if not GCS_AVAILABLE:
            logger.error("❌ GCS components not available")
            return
            
        if not ENQUEUE_AVAILABLE:
            logger.error("❌ Enqueue components not available")
            return
            
        logger.info("✅ All prerequisites available")
        
        # Run the monitoring loop
        asyncio.run(monitor_new_knowledge_entries(args.teacher_id))
        
    except KeyboardInterrupt:
        logger.info("[STOPPED] RAG Processing Scheduler stopped by user")
    except Exception as e:
        logger.error(f"[ERROR] RAG Processing Scheduler failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()