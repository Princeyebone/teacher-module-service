# ✅ Image Upload Fixed - Student Support Pack

## Problem Identified

From the logs:
```
[IMAGE] Error generating image 1: upload_image_to_gcs() missing 1 required positional argument: 'slide_item_id'
```

The `upload_image_to_gcs` function signature was updated but the support pack generator was still using the old signature.

## Function Signature Change

### Old Signature (Incorrect):
```python
upload_image_to_gcs(image_bytes, gcs_path)
# Returns: (public_url, saved_path)
```

### New Signature (Correct):
```python
upload_image_to_gcs(image_bytes: bytes, slide_id: str, slide_item_id: str) -> Optional[str]
# Returns: gcs_path or None
```

## Fix Applied

### Before (Line 364-373):
```python
# Upload to GCS
gcs_path = f"student_support/{pack_id}/image_{i+1}.png"
public_url, saved_path = await upload_image_to_gcs(image_bytes, gcs_path)  # ❌ Wrong signature

images.append({
    "gcs_path": saved_path,
    "alt_text": f"Illustration {i+1} for {topic}",
    "caption": f"Visual aid for understanding {topic}"
})
logger.info(f"[IMAGE] Uploaded image {i+1}")
```

### After (Line 364-376):
```python
# Upload to GCS with new signature (slide_id, slide_item_id)
slide_item_id = f"support_image_{i+1}"
gcs_path = upload_image_to_gcs(image_bytes, pack_id, slide_item_id)  # ✅ Correct signature

if gcs_path:
    images.append({
        "gcs_path": gcs_path,
        "alt_text": f"Illustration {i+1} for {topic}",
        "caption": f"Visual aid for understanding {topic}"
    })
    logger.info(f"[IMAGE] Uploaded image {i+1} to {gcs_path}")
else:
    logger.warning(f"[IMAGE] Failed to upload image {i+1}")
```

## Changes Made

1. **Updated function call** to use 3 parameters: `(image_bytes, pack_id, slide_item_id)`
2. **Removed `await`** - `upload_image_to_gcs` is synchronous, not async
3. **Changed return value handling** - now returns single `gcs_path` or `None`
4. **Added error handling** - checks if `gcs_path` is not None before appending
5. **Improved logging** - shows the actual GCS path in logs

## Image Storage Path

Images are now stored at:
```
slide_images/{pack_id}/support_image_1.png
slide_images/{pack_id}/support_image_2.png
slide_images/{pack_id}/support_image_3.png
```

Example:
```
slide_images/3cf44d18-2397-41e7-970d-0c2e4748199d/support_image_1.png
```

## Benefits

1. **✅ Consistent with slide builder** - Uses same upload function and path structure
2. **✅ Proper error handling** - Won't crash if upload fails
3. **✅ Better logging** - Shows actual GCS paths
4. **✅ Signed URLs** - GCS paths can be used with `generate_signed_url()` for secure access

## Testing

Create a new support pack and check logs for:
```
[IMAGE] Generating image 1/3...
✅ Image generated: 552749 bytes
✅ Image uploaded: slide_images/{pack_id}/support_image_1.png
[IMAGE] Uploaded image 1 to slide_images/{pack_id}/support_image_1.png
```

## Rate Limiting Note

From the logs, you're hitting Vertex AI rate limits (429 errors). This is expected and the image generator has retry logic with exponential backoff (10s, 20s, 40s). Some images may still fail after retries, which is normal for rate-limited APIs.

To reduce rate limiting:
- Generate fewer images (currently 3)
- Add delays between image generation calls
- Use a higher quota Vertex AI project

## Status

✅ **Fixed and ready for testing!**

The worker should auto-reload with the changes. Create a new support pack to test image generation.
