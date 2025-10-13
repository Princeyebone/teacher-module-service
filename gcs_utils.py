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

def generate_signed_url(
    bucket_name: str,
    blob_name: str,
    method: str = "GET",
    content_type: str = "application/octet-stream",
    expiration: int = 86400,
    only_include_host_in_headers: bool = False
) -> str:
    """
    Generate a signed URL for uploading (PUT) or downloading (GET) a file to/from GCS.
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
        method: HTTP method (GET or PUT)
        content_type: Content type of the file
        expiration: Expiration time in seconds
        only_include_host_in_headers: Whether to only include host in signed headers (default: False)
    
    Returns:
        Signed URL for uploading or downloading
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        # Let the GCS library handle URL encoding
        blob = bucket.blob(blob_name)

        logger.info(f"🔗 Generating signed URL for {blob_name} using method {method}")
        logger.info(f"🔗 only_include_host_in_headers: {only_include_host_in_headers}")
        
        # Check if the blob exists for GET requests (only log, don't fail)
        if method.upper() == "GET":
            try:
                if not blob.exists():
                    logger.warning(f"⚠️ Blob {blob_name} does not exist in bucket {bucket_name}")
                else:
                    logger.info(f"✅ Blob {blob_name} exists in bucket {bucket_name}")
            except Exception as e:
                # If we can't check existence due to permissions, that's OK
                logger.info(f"ℹ️ Cannot verify blob existence for {blob_name}: {e}")

        # For PUT requests, we may need to specify headers
        if method.upper() == "PUT":
            # Generate signed URL for upload (HTTP PUT)
            # Only include "host" in signed headers as requested when only_include_host_in_headers is True
            if only_include_host_in_headers:
                logger.info("🔗 Generating PUT URL with only host header")
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method,
                    headers={
                        "host": "storage.googleapis.com"
                    }
                )
            else:
                logger.info("🔗 Generating PUT URL with content-type and host headers")
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method,
                    content_type=content_type,
                    headers={
                        "Content-Type": content_type
                    }
                )
        else:  # GET (download)
            # For GET requests, we typically don't need to specify headers for simple downloads
            # However, if only_include_host_in_headers is True, we'll include the host header
            if only_include_host_in_headers:
                logger.info("🔗 Generating GET URL with host header")
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method,
                    headers={
                        "host": "storage.googleapis.com"
                    }
                )
            else:
                logger.info("🔗 Generating GET URL (no special headers)")
                # For GET requests, we don't need to specify headers, but we should ensure proper authentication
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expiration,
                    method=method
                )

        logger.info(f"✅ Generated signed URL ({method}) for {blob_name}, expires in {expiration}s, only_include_host_in_headers: {only_include_host_in_headers}")
        logger.info(f"✅ URL length: {len(url)} characters")
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
        # Let the GCS library handle URL encoding
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
        # Let the GCS library handle URL encoding
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