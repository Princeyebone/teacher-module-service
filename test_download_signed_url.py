#!/usr/bin/env python3
"""
Test script to verify download signed URL generation and access.
"""

import os
import sys
import requests
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import generate_signed_url, get_gcs_client
from config import settings

def test_download_signed_url():
    """Test download signed URL generation and verification."""
    bucket_name = settings.GCS_BUCKET_NAME
    # Use a realistic file path based on the upload endpoint
    test_blob_name = "sem_plan/test_teacher_id/test_class/test_subject.pdf"
    
    print(f"Testing download signed URL for bucket: {bucket_name}")
    print(f"Test blob name: {test_blob_name}")
    
    # Test generating a download signed URL
    print("\n--- Testing download signed URL generation ---")
    try:
        download_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="GET",
            expiration=604800,  # 7 days
            only_include_host_in_headers=False
        )
        print(f"✅ Download signed URL generated successfully")
        print(f"URL length: {len(download_url)} characters")
        
        # Print a portion of the URL for inspection
        print(f"Generated URL (first 200 chars): {download_url[:200]}...")
        
        # Check key components
        required_params = ["X-Goog-Algorithm", "X-Goog-Credential", "X-Goog-Date", "X-Goog-Expires", "X-Goog-SignedHeaders", "X-Goog-Signature"]
        missing_params = [param for param in required_params if param not in download_url]
        
        if missing_params:
            print(f"❌ Missing required parameters: {missing_params}")
        else:
            print("✅ All required parameters present in signed URL")
            
        # Test accessing the URL (should return 404 since file doesn't exist, but not 403)
        print("\n--- Testing URL accessibility ---")
        try:
            response = requests.get(download_url, timeout=10)
            print(f"HTTP Status Code: {response.status_code}")
            
            if response.status_code == 404:
                print("✅ URL is properly signed (returns 404 for non-existent file, not 403)")
            elif response.status_code == 403:
                print("❌ URL is not properly signed (returns 403 - Access Denied)")
            elif response.status_code == 200:
                print("✅ URL is properly signed and file exists")
            else:
                print(f"⚠️ Unexpected status code: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to access URL: {e}")
            
    except Exception as e:
        print(f"❌ Failed to generate download signed URL: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Download signed URL test completed!")
    return True

if __name__ == "__main__":
    test_download_signed_url()