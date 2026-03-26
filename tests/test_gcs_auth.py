"""Test script for GCS authentication"""

import os
import sys
from app.core.config import settings
from app.services.gcs_utils import get_gcs_client, generate_signed_url, generate_file_name

def test_gcs_authentication():
    """Test that GCS client can be initialized and signed URLs can be generated"""
    try:
        print("Testing GCS authentication...")
        print(f"GCS_PROJECT_ID: {settings.GCS_PROJECT_ID}")
        print(f"GCS_BUCKET_NAME: {settings.GCS_BUCKET_NAME}")
        print(f"GCS_SERVICE_ACCOUNT_JSON: {settings.GCS_SERVICE_ACCOUNT_JSON}")
        
        # Check if service account file exists
        if os.path.exists(settings.GCS_SERVICE_ACCOUNT_JSON):
            print("✅ Service account JSON file exists")
        else:
            print("❌ Service account JSON file not found")
            return False
            
        # Try to initialize GCS client
        print("Initializing GCS client...")
        client = get_gcs_client()
        print("✅ GCS client initialized successfully")
        
        # Try to generate a signed URL
        print("Generating signed URL...")
        teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
        file_name = generate_file_name(teacher_id, "pdf")
        signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, file_name)  # Use default expiration (24 hours)
        print("✅ Signed URL generated successfully")
        print(f"Signed URL: {signed_url[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing GCS authentication: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_gcs_authentication()
    if success:
        print("\n🎉 GCS authentication test passed!")
    else:
        print("\n💥 GCS authentication test failed!")
        sys.exit(1)