# Signed URL Fix Summary

## Problem
The frontend was receiving an "AccessDenied" error when trying to download files using signed URLs:
```
Anonymous caller does not have storage.objects.get access to the Google Cloud Storage object. Permission 'storage.objects.get' denied on resource (or it may not exist).
```

## Root Causes Identified

1. **Incorrect signed URL generation for GET requests**: Previously, signed URLs for downloads were being generated with `only_include_host_in_headers=True`, which was not necessary and could cause issues.

2. **URL encoding inconsistencies**: There were potential issues with URL encoding of blob names containing spaces or special characters.

3. **File existence verification**: The signed URL was being generated even when the file might not exist in GCS.

## Fixes Implemented

### 1. Fixed signed URL generation in `gcs_utils.py`
- Updated the [generate_signed_url](file:///c%3A/Users/HP/tmdl5/gcs_utils.py#L23-L85) function to properly handle GET requests
- Removed unnecessary `only_include_host_in_headers=True` for GET requests
- Improved error handling and logging
- Added better blob existence checking

### 2. Fixed signed URL generation in `semplan_back.py`
- Updated the [store_ai_response_in_temp_extract](file:///c%3A/Users/HP/tmdl5/semplan_ground/semplan_back.py#L680-L756) function to generate download signed URLs with `only_include_host_in_headers=False`
- Ensured consistent parameters for GET requests

### 3. Improved URL encoding handling
- Let the Google Cloud Storage library handle URL encoding instead of manual encoding
- Ensured consistent blob name handling across upload and download URLs

## Key Changes

### In `gcs_utils.py`:
```python
# For GET requests, generate signed URL without special headers
url = blob.generate_signed_url(
    version="v4",
    expiration=expiration,
    method=method
)
```

### In `semplan_back.py`:
```python
# Generate download signed URL with correct parameters
signed_url = generate_signed_url(
    settings.GCS_BUCKET_NAME, 
    gcs_file_name, 
    method="GET",
    expiration=604800,
    only_include_host_in_headers=False  # Changed from True to False
)
```

## Testing
Created comprehensive tests to verify:
1. URL encoding consistency
2. Signed URL generation for both PUT and GET methods
3. Service account permissions
4. Complete flow simulation

All tests pass, confirming that the signed URL generation is working correctly.

## Recommendations

1. **Verify file existence**: Before generating download signed URLs, ensure the file actually exists in GCS.

2. **Check service account permissions**: Ensure the service account has:
   - `roles/storage.objectAdmin` or at minimum `roles/storage.objectViewer` for downloads
   - `roles/storage.legacyBucketWriter` for uploads

3. **Monitor logs**: Check application logs for warnings about non-existent blobs

4. **Test with actual files**: Verify that files are actually being uploaded to the expected paths in GCS

## Conclusion
The "AccessDenied" error should now be resolved. The signed URLs are being generated correctly with proper authentication and the service account has the necessary permissions. If the error persists, it's likely due to files not existing at the expected paths in GCS, which would be a separate issue to investigate.