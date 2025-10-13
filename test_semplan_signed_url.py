#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gcs_utils import generate_signed_url
from config import settings

def test_semplan_signed_url():
    """Test signed URL generation exactly like in semplan_back.py"""
    
    bucket_name = settings.GCS_BUCKET_NAME
    blob_name = "sem_plan/7bed2b69-8000-4b36-8e91-7fe0b70c9d82/Class 10A/Mathematics.docx"
    expiration = 604800  # 7 days
    
    print("Testing signed URL generation exactly like semplan_back.py...")
    print(f"Bucket: {bucket_name}")
    print(f"Blob: {blob_name}")
    print(f"Expiration: {expiration}")
    print(f"only_include_host_in_headers: True")
    print(f"Method: GET (default)")
    
    try:
        # This is exactly what semplan_back.py does
        signed_url = generate_signed_url(
            bucket_name, 
            blob_name, 
            expiration=expiration,
            only_include_host_in_headers=True
        )
        
        print(f"\nGenerated URL: {signed_url}")
        
        # Check the signed headers
        if "X-Goog-SignedHeaders=" in signed_url:
            # Extract the signed headers part
            import urllib.parse
            parsed_url = urllib.parse.urlparse(signed_url)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            signed_headers = query_params.get('X-Goog-SignedHeaders', [''])[0]
            print(f"Signed Headers: {signed_headers}")
            
            # Decode the URL-encoded headers
            decoded_headers = urllib.parse.unquote(signed_headers)
            print(f"Decoded Headers: {decoded_headers}")
            
            # Check if content-type is in the headers
            if "content-type" in decoded_headers.lower():
                print("❌ content-type found in signed headers")
            else:
                print("✅ content-type NOT found in signed headers")
        else:
            print("❌ No X-Goog-SignedHeaders found in URL")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_semplan_signed_url()