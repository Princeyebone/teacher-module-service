#!/usr/bin/env python3
"""
Test script to check GCS permissions and service account configuration.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from gcs_utils import get_gcs_client
from config import settings

def test_gcs_permissions():
    """Test GCS permissions and service account configuration."""
    print("Testing GCS permissions and service account configuration...")
    
    try:
        # Initialize GCS client
        client = get_gcs_client()
        print(f"✅ GCS client initialized successfully")
        print(f"Project ID: {client.project}")
        
        # Check if we can access the bucket
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        print(f"✅ Bucket object created for: {settings.GCS_BUCKET_NAME}")
        
        # Try to check if bucket exists (this requires storage.buckets.get permission)
        try:
            if bucket.exists():
                print(f"✅ Bucket {settings.GCS_BUCKET_NAME} exists and is accessible")
            else:
                print(f"⚠️ Bucket {settings.GCS_BUCKET_NAME} does not exist or is not accessible")
        except Exception as e:
            print(f"⚠️ Cannot check bucket existence: {e}")
            print("This might be due to missing storage.buckets.get permission, which is OK for our use case")
        
        # Test creating a blob object (this doesn't require any permissions yet)
        test_blob_name = "test_permissions_check.txt"
        blob = bucket.blob(test_blob_name)
        print(f"✅ Blob object created for: {test_blob_name}")
        
        # Try to check if blob exists (this requires storage.objects.get permission)
        try:
            if blob.exists():
                print(f"✅ Blob {test_blob_name} exists")
            else:
                print(f"✅ Blob {test_blob_name} does not exist (but we have permission to check)")
        except Exception as e:
            print(f"❌ Cannot check blob existence: {e}")
            print("This indicates a permissions issue with storage.objects.get")
            return False
            
        print("\n✅ GCS permissions test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize GCS client: {e}")
        return False

if __name__ == "__main__":
    success = test_gcs_permissions()
    if success:
        print("\n🎉 GCS permissions are properly configured!")
    else:
        print("\n💥 GCS permissions issue detected!")
        print("Please check that your service account has the following roles:")
        print("- roles/storage.objectAdmin (or at minimum roles/storage.objectViewer for downloads)")
        print("- roles/storage.legacyBucketWriter (for uploads)")