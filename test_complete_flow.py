#!/usr/bin/env python3
"""
Test script to simulate the complete flow and verify signed URL generation for semester plans.
"""

import os
import sys
import uuid
import urllib.parse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import generate_signed_url
from config import settings

def test_complete_flow():
    """Test the complete flow for semester plan file handling."""
    # Simulate the exact flow from the application
    teacher_id = "123e4567-e89b-12d3-a456-426614174000"  # Example UUID
    class_name = "Grade 6"
    subject = "Mathematics"
    file_ext = "pdf"
    
    print("Testing complete semester plan flow...")
    print(f"Teacher ID: {teacher_id}")
    print(f"Class: {class_name}")
    print(f"Subject: {subject}")
    
    # Step 1: Generate GCS file name (as done in sem_file_handler.py upload endpoint)
    gcs_file_name = f"sem_plan/{teacher_id}/{class_name}/{subject}.{file_ext}"
    print(f"\nStep 1: Generated GCS file name: {gcs_file_name}")
    
    # Step 2: Generate upload signed URL (as done in sem_file_handler.py upload endpoint)
    print("\nStep 2: Generating upload signed URL...")
    try:
        upload_url = generate_signed_url(
            bucket_name=settings.GCS_BUCKET_NAME,
            blob_name=gcs_file_name,
            method="PUT",
            content_type="application/pdf",
            expiration=3600,  # 1 hour
            only_include_host_in_headers=False
        )
        print(f"✅ Upload signed URL generated successfully")
        print(f"URL length: {len(upload_url)} characters")
    except Exception as e:
        print(f"❌ Failed to generate upload signed URL: {e}")
        return False
    
    # Step 3: Simulate file upload (we won't actually upload, just verify the URL)
    print("\nStep 3: Simulating file upload...")
    print("✅ File upload simulation complete")
    
    # Step 4: Generate download signed URL (as done in semplan_back.py store_ai_response_in_temp_extract)
    print("\nStep 4: Generating download signed URL...")
    try:
        download_url = generate_signed_url(
            bucket_name=settings.GCS_BUCKET_NAME,
            blob_name=gcs_file_name,
            method="GET",
            expiration=604800,  # 7 days
            only_include_host_in_headers=False
        )
        print(f"✅ Download signed URL generated successfully")
        print(f"URL length: {len(download_url)} characters")
    except Exception as e:
        print(f"❌ Failed to generate download signed URL: {e}")
        return False
    
    # Step 5: Verify the download URL structure
    print("\nStep 5: Verifying download URL structure...")
    
    # Check for required parameters
    required_params = ["X-Goog-Algorithm", "X-Goog-Credential", "X-Goog-Date", "X-Goog-Expires", "X-Goog-SignedHeaders", "X-Goog-Signature"]
    missing_params = [param for param in required_params if param not in download_url]
    
    if missing_params:
        print(f"❌ Download URL missing required parameters: {missing_params}")
        return False
    else:
        print("✅ Download URL has all required parameters")
    
    # Step 6: Check if the blob name in the URL matches what we expect (accounting for URL encoding)
    print("\nStep 6: Verifying blob name in download URL...")
    
    # Extract the blob name from the URL
    bucket_prefix = f"https://storage.googleapis.com/{settings.GCS_BUCKET_NAME}/"
    if download_url.startswith(bucket_prefix):
        # Extract the part after the bucket name and before query parameters
        blob_part = download_url[len(bucket_prefix):]
        query_start = blob_part.find("?")
        if query_start != -1:
            blob_in_url = blob_part[:query_start]
        else:
            blob_in_url = blob_part
            
        print(f"Blob name in URL (encoded): {blob_in_url}")
        print(f"Expected blob name (unencoded): {gcs_file_name}")
        
        # URL decode the blob name from the URL and compare
        decoded_blob_in_url = urllib.parse.unquote(blob_in_url)
        print(f"Blob name in URL (decoded): {decoded_blob_in_url}")
        
        if decoded_blob_in_url == gcs_file_name:
            print("✅ Blob name in URL matches expected value when URL decoded")
        else:
            print("❌ Blob name in URL does not match expected value")
            return False
    else:
        print("❌ Download URL does not have expected prefix")
        return False
    
    print("\n✅ Complete flow test passed!")
    return True

if __name__ == "__main__":
    success = test_complete_flow()
    if success:
        print("\n🎉 All tests passed! The signed URL generation should work correctly.")
    else:
        print("\n💥 Tests failed! There may be an issue with the signed URL generation.")