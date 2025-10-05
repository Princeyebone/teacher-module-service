"""Google Cloud Storage utilities for timetable file handling"""

import os
import uuid
from typing import Optional
from google.cloud import storage
from google.cloud.exceptions import NotFound
from logger import logger
from config import settings

# Initialize GCS client
def get_gcs_client():
    """Initialize and return GCS client"""
    try:
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

def generate_signed_url(bucket_name: str, blob_name: str, content_type: str = "application/octet-stream", expiration: int = 86400) -> str:
    """
    Generate a signed URL for uploading a file to GCS
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
        content_type: Content type of the file (default: application/octet-stream)
        expiration: Expiration time in seconds (default: 24 hours)
    
    Returns:
        Signed URL for uploading
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        # Log the parameters
        logger.info(f"🔗 Generating signed URL for {blob_name}")
        logger.info(f"📦 Bucket: {bucket_name}, Content-Type: {content_type}, Expiration: {expiration} seconds")
        
        # Generate signed URL for upload (HTTP PUT)
        # Include content-type in signed headers to match frontend expectations
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="PUT",
            content_type=content_type,
            headers={
                "Content-Type": content_type
            }
        )
        
        logger.info(f"✅ Generated signed URL for {blob_name} with content-type {content_type}, expiring in {expiration} seconds")
        logger.info(f"📏 Signed URL length: {len(url)} characters")
        return url
    except Exception as e:
        logger.error(f"💥 Failed to generate signed URL: {e}", exc_info=True)
        raise

def generate_file_name(teacher_id: str, file_extension: str, file_type: str = "timetable") -> str:
    """
    Generate a file name in the format: {file_type}/{teacher_id}.{extension}
    
    Args:
        teacher_id: Teacher UUID
        file_extension: File extension (e.g., 'pdf', 'docx')
        file_type: Type of file (default: 'timetable', can be 'academic_calendar', etc.)
    
    Returns:
        Generated file name
    """
    return f"{file_type}/{teacher_id}.{file_extension}"

def get_file_from_gcs(bucket_name: str, blob_name: str) -> Optional[bytes]:
    """
    Download file content from GCS
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
    
    Returns:
        File content as bytes, or None if not found
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            content = blob.download_as_bytes()
            logger.info(f"✅ Downloaded file {blob_name} from GCS")
            return content
        else:
            logger.warning(f"⚠️ File {blob_name} not found in GCS")
            return None
    except NotFound:
        logger.warning(f"⚠️ File {blob_name} not found in GCS")
        return None
    except Exception as e:
        logger.error(f"💥 Failed to download file from GCS: {e}")
        raise

def delete_file_from_gcs(bucket_name: str, blob_name: str) -> bool:
    """
    Delete file from GCS
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
    
    Returns:
        True if file was deleted, False if not found
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        if blob.exists():
            blob.delete()
            logger.info(f"🗑️ Deleted file {blob_name} from GCS")
            return True
        else:
            logger.warning(f"⚠️ File {blob_name} not found in GCS for deletion")
            return False
    except Exception as e:
        logger.error(f"💥 Failed to delete file from GCS: {e}")
        raise