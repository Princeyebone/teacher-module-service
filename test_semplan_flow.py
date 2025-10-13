#!/usr/bin/env python3
"""
Test script to simulate the complete semester plan flow and verify signed URL generation.
"""

import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import generate_signed_url
from config import settings

def simulate_semplan_flow():
    """Simulate the complete semester plan flow."""
    teacher_id = str(uuid.uuid4())
    class_name = "Grade 6"
    subject = "Mathematics"
    file_ext = "pdf"
    
    print("Simulating semester plan flow...")
    print(f"Teacher ID: {teacher_id}")
    print(f"Class: {class_name}")
    print(f"Subject: {subject}")
    
    # Step 1: Generate GCS file name (as done in upload endpoint)
    gcs_file_name = f"sem_plan/{teacher_id}/{class_name}/{subject}.{file_ext}"
    print(f"\nStep 1: Generated GCS file name: {gcs_file_name}")
    
    # Step 2: Generate upload signed URL (as done in upload endpoint)
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
    
    # Step 3: Generate download signed URL (as done in background processing)
    print("\nStep 3: Generating download signed URL...")
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
    
    # Step 4: Verify both URLs have the correct structure
    print("\nStep 4: Verifying URL structures...")
    
    # Check upload URL
    upload_required_params = ["X-Goog-Algorithm", "X-Goog-Credential", "X-Goog-Date", "X-Goog-Expires", "X-Goog-SignedHeaders", "X-Goog-Signature"]
    missing_upload_params = [param for param in upload_required_params if param not in upload_url]
    
    if missing_upload_params:
        print(f"❌ Upload URL missing required parameters: {missing_upload_params}")
    else:
        print("✅ Upload URL has all required parameters")
    
    # Check download URL
    download_required_params = ["X-Goog-Algorithm", "X-Goog-Credential", "X-Goog-Date", "X-Goog-Expires", "X-Goog-SignedHeaders", "X-Goog-Signature"]
    missing_download_params = [param for param in download_required_params if param not in download_url]
    
    if missing_download_params:
        print(f"❌ Download URL missing required parameters: {missing_download_params}")
    else:
        print("✅ Download URL has all required parameters")
    
    # Step 5: Compare the blob names in both URLs
    print("\nStep 5: Comparing blob names in URLs...")
    
    # Extract blob name from URLs (everything after the bucket name and before the query parameters)
    upload_blob_start = upload_url.find(f"{settings.GCS_BUCKET_NAME}/") + len(f"{settings.GCS_BUCKET_NAME}/")
    upload_blob_end = upload_url.find("?", upload_blob_start)
    upload_blob_name = upload_url[upload_blob_start:upload_blob_end] if upload_blob_end != -1 else upload_url[upload_blob_start:]
    
    download_blob_start = download_url.find(f"{settings.GCS_BUCKET_NAME}/") + len(f"{settings.GCS_BUCKET_NAME}/")
    download_blob_end = download_url.find("?", download_blob_start)
    download_blob_name = download_url[download_blob_start:download_blob_end] if download_blob_end != -1 else download_url[download_blob_start:]
    
    print(f"Upload blob name: {upload_blob_name}")
    print(f"Download blob name: {download_blob_name}")
    
    if upload_blob_name == download_blob_name == gcs_file_name:
        print("✅ Blob names match in both URLs")
    else:
        print("❌ Blob names don't match")
        return False
    
    print("\n✅ Semester plan flow simulation completed successfully!")
    return True

if __name__ == "__main__":
    simulate_semplan_flow()