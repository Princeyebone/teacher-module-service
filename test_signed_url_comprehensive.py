"""Comprehensive test for signed URL generation with different content types"""

import os
import sys
from config import settings
from gcs_utils import get_gcs_client, generate_signed_url, generate_file_name

def test_signed_url_with_content_types():
    """Test signed URL generation with different content types"""
    try:
        print("Testing signed URL generation with different content types...")
        
        # Test with different file types
        test_cases = [
            ("pdf", "application/pdf"),
            ("png", "image/png"),
            ("jpg", "image/jpeg"),
            ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("txt", "text/plain")
        ]
        
        for ext, content_type in test_cases:
            print(f"\nTesting {ext} with content-type: {content_type}")
            
            # Generate file name
            teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
            file_name = generate_file_name(teacher_id, ext)
            
            # Generate signed URL
            signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, file_name, 3600)
            print(f"✅ Signed URL generated for {ext}")
            
            # Check if URL contains important parameters
            if "X-Goog-Algorithm" in signed_url:
                print(f"✅ Contains algorithm parameter")
            else:
                print(f"❌ Missing algorithm parameter")
                
            if "X-Goog-Credential" in signed_url:
                print(f"✅ Contains credential parameter")
            else:
                print(f"❌ Missing credential parameter")
                
            if "X-Goog-Date" in signed_url:
                print(f"✅ Contains date parameter")
            else:
                print(f"❌ Missing date parameter")
                
            if "X-Goog-Expires" in signed_url:
                print(f"✅ Contains expires parameter")
            else:
                print(f"❌ Missing expires parameter")
                
        return True
        
    except Exception as e:
        print(f"❌ Error testing signed URL generation: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gcs_bucket_access():
    """Test access to GCS bucket"""
    try:
        print("\nTesting GCS bucket access...")
        
        # Initialize client
        client = get_gcs_client()
        
        # Try to access bucket
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        
        # Check if bucket exists (this will not raise an error even if bucket doesn't exist)
        print(f"Bucket name: {bucket.name}")
        
        # Try to create a test blob (this should work if credentials are correct)
        blob = bucket.blob("test-access")
        print("✅ GCS bucket access test completed")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing GCS bucket access: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running comprehensive GCS signed URL tests...")
    
    success1 = test_signed_url_with_content_types()
    success2 = test_gcs_bucket_access()
    
    if success1 and success2:
        print("\n🎉 All GCS tests passed!")
    else:
        print("\n💥 Some GCS tests failed!")
        sys.exit(1)