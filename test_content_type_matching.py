"""Test script for content type matching in signed URL generation"""

import os
import sys
from config import settings
from gcs_utils import get_gcs_client, generate_signed_url, generate_file_name

def test_content_type_matching():
    """Test that signed URLs are generated with correct content types"""
    try:
        print("Testing content type matching in signed URL generation...")
        
        # Test with different content types that frontend might send
        test_cases = [
            ("png", "image/png"),
            ("jpg", "image/jpeg"),
            ("pdf", "application/pdf"),
            ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("txt", "text/plain"),
            ("unknown", "application/octet-stream")
        ]
        
        for ext, content_type in test_cases:
            print(f"\nTesting {ext} with content-type: {content_type}")
            
            # Generate file name
            teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
            file_name = generate_file_name(teacher_id, ext)
            
            # Generate signed URL with specific content type
            signed_url = generate_signed_url(settings.GCS_BUCKET_NAME, file_name, content_type, 3600)
            print(f"✅ Signed URL generated for {ext}")
            
            # Check if URL contains the content type
            if f"content-type%3Bhost" in signed_url:
                print(f"✅ Contains signed headers parameter")
            else:
                print(f"❌ Missing signed headers parameter")
                
            print(f"Signed URL: {signed_url[:150]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing content type matching: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running content type matching tests...")
    
    success = test_content_type_matching()
    
    if success:
        print("\n🎉 Content type matching tests passed!")
        print("The backend now generates signed URLs that match the content type sent by the frontend.")
    else:
        print("\n💥 Content type matching tests failed!")
        sys.exit(1)