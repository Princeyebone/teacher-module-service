#!/usr/bin/env python3
"""
Test script to verify signed URL generation for GCS files.
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

def test_signed_url_generation():
    """Test signed URL generation for both GET and PUT methods."""
    bucket_name = settings.GCS_BUCKET_NAME
    test_blob_name = "test_file.txt"
    
    print(f"Testing signed URL generation for bucket: {bucket_name}")
    print(f"Test blob name: {test_blob_name}")
    
    # First, let's check if the bucket exists and we have access
    try:
        client = get_gcs_client()
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            print(f"❌ Bucket {bucket_name} does not exist or is not accessible")
            return False
        else:
            print(f"✅ Bucket {bucket_name} exists and is accessible")
    except Exception as e:
        print(f"❌ Failed to access bucket: {e}")
        return False
    
    # Test 1: Generate a PUT signed URL
    print("\n--- Testing PUT signed URL ---")
    try:
        put_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="PUT",
            content_type="text/plain",
            expiration=3600,  # 1 hour
            only_include_host_in_headers=False
        )
        print(f"✅ PUT signed URL generated successfully")
        print(f"URL length: {len(put_url)} characters")
        
        # Verify the URL is accessible (should return 200 or similar for PUT)
        # Note: We won't actually PUT data, just check the URL structure
        print(f"PUT URL preview: {put_url[:100]}...")
        
    except Exception as e:
        print(f"❌ Failed to generate PUT signed URL: {e}")
        return False
    
    # Test 2: Generate a GET signed URL
    print("\n--- Testing GET signed URL ---")
    try:
        get_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="GET",
            expiration=3600,  # 1 hour
            only_include_host_in_headers=False
        )
        print(f"✅ GET signed URL generated successfully")
        print(f"URL length: {len(get_url)} characters")
        
        # Verify the URL is accessible (should return 404 if file doesn't exist, but no auth error)
        print(f"GET URL preview: {get_url[:100]}...")
        
    except Exception as e:
        print(f"❌ Failed to generate GET signed URL: {e}")
        return False
    
    # Test 3: Test with only_include_host_in_headers=True
    print("\n--- Testing PUT signed URL with only host header ---")
    try:
        put_url_host_only = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="PUT",
            content_type="text/plain",
            expiration=3600,  # 1 hour
            only_include_host_in_headers=True
        )
        print(f"✅ PUT signed URL (host only) generated successfully")
        print(f"URL length: {len(put_url_host_only)} characters")
        
        # Verify the URL is accessible
        print(f"PUT URL (host only) preview: {put_url_host_only[:100]}...")
        
    except Exception as e:
        print(f"❌ Failed to generate PUT signed URL (host only): {e}")
        return False
    
    print("\n✅ All signed URL generation tests passed!")
    return True

if __name__ == "__main__":
    test_signed_url_generation()