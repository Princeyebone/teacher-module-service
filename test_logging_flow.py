"""Test script to verify the complete logging flow"""

import logging
from file_handler.tm_file_handler import generate_file_name
from gcs_utils import generate_signed_url
from config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_complete_flow():
    """Test the complete flow with logging"""
    try:
        logger.info("=== Testing Complete Flow with Logging ===")
        
        # Step 1: Generate file name
        teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
        file_ext = "pdf"
        gcs_file_name = generate_file_name(teacher_id, file_ext)
        logger.info(f"Step 1 - Generated GCS file name: {gcs_file_name}")
        
        # Step 2: Generate signed URL
        content_type = "application/pdf"
        signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, gcs_file_name, content_type)
        logger.info(f"Step 2 - Generated signed URL (length: {len(signed_url)} characters)")
        
        # Step 3: Show what would be sent to frontend
        logger.info("Step 3 - Data that would be sent to frontend:")
        logger.info(f"  - Signed URL: {signed_url[:100]}...")
        logger.info(f"  - GCS File Name: {gcs_file_name}")
        logger.info(f"  - Content Type: {content_type}")
        
        # Step 4: Show what happens in backend processing
        logger.info("Step 4 - Backend processing flow:")
        logger.info("  - File received and saved locally")
        logger.info("  - Text extracted from file")
        logger.info(f"  - GCS path: gs://{settings.GCS_BUCKET_NAME}/{gcs_file_name}")
        logger.info("  - Data sent to AI for processing")
        logger.info("  - AI response received and parsed")
        logger.info("  - Results sent via WebSocket")
        
        logger.info("=== Complete Flow Test Successful ===")
        return True
        
    except Exception as e:
        logger.error(f"Error in complete flow test: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    test_complete_flow()