# GCS Authentication and Signature Fix Summary

## Issues Identified

1. **"ExpiredToken" Error**: Signed URLs were expiring after 1 hour (3600 seconds)
2. **"SignatureDoesNotMatch" Error**: Request signature didn't match the signature provided by GCS due to content-type mismatch

## Fixes Applied

### 1. Increased Expiration Time
- Updated [gcs_utils.py](file:///c%3A/Users/HP/tmdl5/gcs_utils.py) to use 24-hour expiration (86400 seconds) instead of 1 hour
- This resolves the "ExpiredToken" error

### 2. Fixed Service Account Configuration
- Updated [.env](file:///c%3A/Users/HP/tmdl5/.env) file to use absolute path for [GCS_SERVICE_ACCOUNT_JSON](file://c:\Users\HP\tmdl5\config.py#L18-L18)
- Changed from: `teachermodule-728d7a044c34.json`
- Changed to: `c:\Users\HP\tmdl5\teachermodule-728d7a044c34.json`

### 3. Enhanced Signed URL Generation with Content-Type Matching
- Modified [generate_signed_url](file:///c%3A/Users/HP/tmdl5/gcs_utils.py#L26-L55) function to accept content_type parameter
- Updated [tm_file_handler.py](file:///c%3A/Users/HP/tmdl5/file_handler/tm_file_handler.py) to pass the actual content type from the uploaded file
- Return content_type in the response so frontend can use it for the upload
- This resolves the "SignatureDoesNotMatch" error by ensuring the signed URL matches the content type the frontend will send

## Root Cause of SignatureDoesNotMatch Error

The error was caused by a mismatch between:
- What was signed in the URL: `content-type:application/octet-stream` (default)
- What the frontend was sending: `content-type:image/png` (actual file type)

## Verification

Tests confirmed that:
- ✅ Service account JSON file exists and is accessible
- ✅ GCS client can be initialized successfully
- ✅ Signed URLs can be generated for all file types with correct content types
- ✅ Signed URLs contain all required parameters
- ✅ GCS bucket access works correctly

## Current Status

The backend is now correctly generating signed URLs for GCS uploads that match the content type of the files being uploaded. This should resolve both the "ExpiredToken" and "SignatureDoesNotMatch" errors.

## Next Steps

1. Update frontend to use the content_type returned by the backend when uploading to GCS
2. Test the upload process again with the fixed backend
3. Monitor for any remaining authentication issues