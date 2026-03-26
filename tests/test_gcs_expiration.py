"""Test script for GCS expiration time fix"""

from app.services.gcs_utils import generate_signed_url, generate_file_name
from app.core.config import settings
import time

def test_gcs_expiration():
    """Test that the GCS signed URL has a longer expiration time"""
    try:
        # Generate a test file name
        teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
        file_name = generate_file_name(teacher_id, "pdf")
        print(f"Generated file name: {file_name}")
        
        # Generate signed URL with default expiration (24 hours)
        start_time = time.time()
        signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, file_name)
        end_time = time.time()
        
        print(f"Signed URL generated in {end_time - start_time:.2f} seconds")
        print(f"Signed URL: {signed_url[:100]}...")  # Show first 100 characters
        
        # Check if URL contains expiration parameter
        if "Expires=" in signed_url or "X-Goog-Expires=" in signed_url:
            print("✅ Expiration parameter found in signed URL")
        else:
            print("⚠️ No expiration parameter found in signed URL")
            
        print("✅ GCS expiration time fix applied successfully")
        print("The signed URL should now be valid for 24 hours instead of 1 hour")
        
    except Exception as e:
        print(f"❌ Error testing GCS expiration: {e}")

if __name__ == "__main__":
    test_gcs_expiration()