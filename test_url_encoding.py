#!/usr/bin/env python3
"""
Test script to verify URL encoding consistency in signed URLs.
"""

import os
import sys
import urllib.parse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import generate_signed_url
from config import settings

def test_url_encoding():
    """Test URL encoding consistency."""
    bucket_name = settings.GCS_BUCKET_NAME
    # Test with a blob name that contains spaces
    blob_name = "sem_plan/test_teacher/Grade 6/Mathematics.pdf"
    
    print(f"Testing URL encoding for bucket: {bucket_name}")
    print(f"Blob name: {blob_name}")
    
    # Generate upload URL
    print("\n--- Generating upload URL ---")
    try:
        upload_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=blob_name,
            method="PUT",
            content_type="application/pdf",
            expiration=3600
        )
        print(f"✅ Upload URL generated")
        print(f"Upload URL: {upload_url}")
    except Exception as e:
        print(f"❌ Failed to generate upload URL: {e}")
        return False
    
    # Generate download URL
    print("\n--- Generating download URL ---")
    try:
        download_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=blob_name,
            method="GET",
            expiration=604800
        )
        print(f"✅ Download URL generated")
        print(f"Download URL: {download_url}")
    except Exception as e:
        print(f"❌ Failed to generate download URL: {e}")
        return False
    
    # Extract the blob path from both URLs and compare
    print("\n--- Comparing blob paths in URLs ---")
    
    def extract_blob_path(url):
        # Find the part after the bucket name
        bucket_part = f"{bucket_name}/"
        start_idx = url.find(bucket_part)
        if start_idx == -1:
            return None
        start_idx += len(bucket_part)
        
        # Find the end (before query parameters)
        end_idx = url.find("?", start_idx)
        if end_idx == -1:
            end_idx = len(url)
            
        return url[start_idx:end_idx]
    
    upload_blob_path = extract_blob_path(upload_url)
    download_blob_path = extract_blob_path(download_url)
    
    print(f"Upload blob path: {upload_blob_path}")
    print(f"Download blob path: {download_blob_path}")
    
    # They should be the same when URL decoded
    if upload_blob_path and download_blob_path:
        decoded_upload = urllib.parse.unquote(upload_blob_path)
        decoded_download = urllib.parse.unquote(download_blob_path)
        
        print(f"Decoded upload path: {decoded_upload}")
        print(f"Decoded download path: {decoded_download}")
        
        if decoded_upload == decoded_download == blob_name:
            print("✅ Blob paths match when URL decoded")
            return True
        else:
            print("❌ Blob paths don't match when URL decoded")
            return False
    else:
        print("❌ Could not extract blob paths from URLs")
        return False

if __name__ == "__main__":
    success = test_url_encoding()
    if success:
        print("\n✅ URL encoding test passed!")
    else:
        print("\n❌ URL encoding test failed!")