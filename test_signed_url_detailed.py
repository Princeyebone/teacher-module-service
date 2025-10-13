#!/usr/bin/env python3
"""
Detailed test script to verify signed URL generation for GCS files.
This script focuses on the URL generation process rather than bucket access.
"""

import os
import sys
import requests
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import generate_signed_url
from config import settings

def test_signed_url_structure():
    """Test the structure of generated signed URLs without accessing GCS."""
    bucket_name = "teacher_module_acatable_bucket"
    test_blob_name = "semester_plans/test_plan.pdf"
    
    print(f"Testing signed URL structure for bucket: {bucket_name}")
    print(f"Test blob name: {test_blob_name}")
    
    # Test 1: Generate a GET signed URL (this is what's used for downloads)
    print("\n--- Testing GET signed URL structure ---")
    try:
        get_url = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="GET",
            expiration=604800,  # 7 days
            only_include_host_in_headers=False
        )
        print(f"✅ GET signed URL generated successfully")
        print(f"URL length: {len(get_url)} characters")
        
        # Analyze the URL structure
        print(f"Generated URL: {get_url}")
        
        # Check for key components in the signed URL
        if "GoogleAccessId" in get_url:
            print("✅ URL contains GoogleAccessId parameter")
        else:
            print("❌ URL missing GoogleAccessId parameter")
            
        if "Signature" in get_url:
            print("✅ URL contains Signature parameter")
        else:
            print("❌ URL missing Signature parameter")
            
        if "Expires" in get_url:
            print("✅ URL contains Expires parameter")
        else:
            print("❌ URL missing Expires parameter")
        
        # Check if URL starts with the correct prefix
        expected_prefix = f"https://storage.googleapis.com/{bucket_name}/{test_blob_name}"
        if get_url.startswith(expected_prefix):
            print("✅ URL has correct prefix")
        else:
            print(f"❌ URL prefix mismatch. Expected: {expected_prefix}")
        
    except Exception as e:
        print(f"❌ Failed to generate GET signed URL: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Generate a GET signed URL with only host header
    print("\n--- Testing GET signed URL with only host header ---")
    try:
        get_url_host_only = generate_signed_url(
            bucket_name=bucket_name,
            blob_name=test_blob_name,
            method="GET",
            expiration=604800,  # 7 days
            only_include_host_in_headers=True
        )
        print(f"✅ GET signed URL (host only) generated successfully")
        print(f"URL length: {len(get_url_host_only)} characters")
        
        # Analyze the URL structure
        print(f"Generated URL: {get_url_host_only}")
        
    except Exception as e:
        print(f"❌ Failed to generate GET signed URL (host only): {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Signed URL structure tests completed!")
    return True

if __name__ == "__main__":
    test_signed_url_structure()