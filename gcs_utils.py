"""
Google Cloud Storage Utility Functions

This module provides utility functions for working with Google Cloud Storage,
including generating signed URLs and downloading files.
"""

import os
from typing import Optional
from config import settings
from logger import logger

def get_gcs_client():
    """Initialize and return GCS client"""
    try:
        from google.cloud import storage
        
        if settings.GCS_SERVICE_ACCOUNT_JSON:
            # If service account JSON is provided as content
            if settings.GCS_SERVICE_ACCOUNT_JSON.startswith('{'):
                import json
                from google.oauth2 import service_account
                credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                client = storage.Client(credentials=credentials, project=settings.GCS_PROJECT_ID)
            # If service account JSON is provided as file path
            else:
                client = storage.Client.from_service_account_json(
                    settings.GCS_SERVICE_ACCOUNT_JSON, 
                    project=settings.GCS_PROJECT_ID
                )
        else:
            # Use default credentials (for development)
            client = storage.Client(project=settings.GCS_PROJECT_ID)
        return client
    except Exception as e:
        logger.error(f"❌ Failed to initialize GCS client: {e}")
        raise

def get_file_from_gcs(bucket_name: str, blob_name: str) -> Optional[bytes]:
    """
    Download file content from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
        
    Returns:
        File content as bytes, or None if download failed
    """
    try:
        logger.info(f"📥 Downloading file from GCS: {bucket_name}/{blob_name}")
        
        # Get GCS client
        client = get_gcs_client()
        
        # Get bucket and blob
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Download content as bytes
        content = blob.download_as_bytes()
        
        logger.info(f"✅ Successfully downloaded {len(content)} bytes from GCS")
        return content
        
    except Exception as e:
        logger.error(f"❌ Error downloading file from GCS: {e}")
        return None

def generate_signed_url(bucket_name: str, blob_name: str, method: str = "GET", 
                       content_type: Optional[str] = None, expiration: int = 86400) -> Optional[str]:
    """
    Generate a signed URL for a GCS blob.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
        method: HTTP method (GET, PUT, POST, etc.)
        content_type: Content type for PUT/POST requests
        expiration: URL expiration time in seconds (default: 24 hours)
        
    Returns:
        Signed URL string, or None if generation failed
    """
    try:
        logger.info(f"🔗 Generating signed URL for GCS: {bucket_name}/{blob_name}")
        
        # Get GCS client
        client = get_gcs_client()
        
        # Get bucket and blob
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Determine response content type based on file extension for GET requests
        ext = blob_name.lower().split('.')[-1] if '.' in blob_name else ''
        content_type_map = {
            'mp3': 'audio/mpeg',
            'wav': 'audio/wav',
            'ogg': 'audio/ogg',
            'webm': 'audio/webm',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'svg': 'image/svg+xml',
            'pdf': 'application/pdf',
        }
        response_type = content_type_map.get(ext, None)
        
        # Generate signed URL with proper content type header
        # This prevents ERR_BLOCKED_BY_ORB in browsers
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method=method,
            content_type=content_type,
            response_type=response_type if method == "GET" else None
        )
        
        logger.info(f"✅ Generated signed URL: {url}")
        return url
        
    except Exception as e:
        logger.error(f"❌ Error generating signed URL: {e}")
        return None


def generate_file_name(teacher_id: str, file_ext: str, folder: str = "uploads", 
                      pillar: str = "general", original_filename: str = None) -> str:
    """
    Generate a standardized file name for GCS storage.
    
    Args:
        teacher_id: Teacher UUID string
        file_ext: File extension (without dot)
        folder: Main folder name (default: "uploads")
        pillar: Knowledge pillar (default: "general")
        original_filename: Original filename for reference (optional)
        
    Returns:
        Generated file path string
    """
    import uuid
    from datetime import datetime
    
    # Generate timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Generate unique identifier
    unique_id = str(uuid.uuid4())[:8]
    
    # Create filename
    if original_filename:
        # Use original filename without extension and add our metadata
        base_name = os.path.splitext(original_filename)[0]
        filename = f"{base_name}_{timestamp}_{unique_id}.{file_ext}"
    else:
        # Generic filename
        filename = f"{timestamp}_{unique_id}.{file_ext}"
    
    # Create full path
    file_path = f"{folder}/{teacher_id}/{pillar}/{filename}"
    
    logger.info(f"📂 Generated file path: {file_path}")
    return file_path