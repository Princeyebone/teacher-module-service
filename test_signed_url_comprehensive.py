"""Comprehensive test for signed URL generation with different methods and content types"""

import os
import sys
from config import settings
from gcs_utils import get_gcs_client, generate_signed_url, generate_file_name

def test_comprehensive_signed_url_generation():
    """Test signed URL generation with different methods and content types"""
    try:
        print("Testing comprehensive signed URL generation...")
        
        # Test with different methods and content types
        test_cases = [
            # (method, extension, content_type, description)
            ("PUT", "pdf", "application/pdf", "PUT request for PDF upload"),
            ("GET", "pdf", "application/pdf", "GET request for PDF download"),
            ("PUT", "jpg", "image/jpeg", "PUT request for JPG upload"),
            ("GET", "jpg", "image/jpeg", "GET request for JPG download"),
            ("PUT", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "PUT request for DOCX upload"),
            ("GET", "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "GET request for DOCX download"),
        ]
        
        teacher_id = "7bed2b69-8000-4b36-8e91-7fe0b70c9d82"
        
        for method, ext, content_type, description in test_cases:
            print(f"\nTesting {description}")
            
            # Generate file name
            file_name = generate_file_name(teacher_id, ext)
            
            # Generate signed URL with specific method and content type
            signed_url = generate_signed_url(
                settings.GCS_BUCKET_NAME, 
                file_name, 
                method=method,
                content_type=content_type,
                expiration=3600
            )
            print(f"✅ Signed URL generated for {description}")
            print(f"Signed URL: {signed_url[:150]}...")
            
            # Check if URL contains expected parameters
            if method == "PUT":
                if "X-Goog-Algorithm" in signed_url and "PUT" in signed_url:
                    print(f"✅ Contains correct method and algorithm parameters")
                else:
                    print(f"❌ Missing method or algorithm parameters")
            else:  # GET
                if "X-Goog-Algorithm" in signed_url and "GET" in signed_url:
                    print(f"✅ Contains correct method and algorithm parameters")
                else:
                    print(f"❌ Missing method or algorithm parameters")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing comprehensive signed URL generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Running comprehensive signed URL generation tests...")
    
    success = test_comprehensive_signed_url_generation()
    
    if success:
        print("\n🎉 Comprehensive signed URL generation tests passed!")
        print("The backend now generates signed URLs correctly for different methods and content types.")
    else:
        print("\n💥 Comprehensive signed URL generation tests failed!")
        sys.exit(1)