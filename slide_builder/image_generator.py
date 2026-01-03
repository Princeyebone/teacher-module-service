"""
Image Generator for Slide Builder

Generates educational images using Vertex AI Imagen.
Called after slide generation to process pending image prompts.

Features:
- Batch processing for speed (parallel generation)
- Rate limiting to avoid API throttling
- GCS upload with signed URLs for secure access
"""

import asyncio
import base64
import aiohttp
from typing import Optional, Dict, Any, List
from uuid import UUID
import json

from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google.cloud import storage

from sqlalchemy import text
from database import get_db
from config import settings

# Logging
import logging
image_logger = logging.getLogger("slide_builder.image_generator")
image_logger.setLevel(logging.INFO)

# Configuration for rate limiting
BATCH_SIZE = 2  # Number of images per batch (reduced for rate limiting)
MAX_RETRIES = 3  # Retries per image on failure
DELAY_BETWEEN_IMAGES = 3  # Seconds to wait between images in a batch
DELAY_BETWEEN_BATCHES = 5  # Seconds to wait between batches
RATE_LIMIT_BACKOFF_BASE = 10  # Base seconds to wait when rate limited


async def generate_image_with_vertex(prompt: str, retry_count: int = 0) -> Optional[bytes]:
    """
    Generate an image using Vertex AI Imagen 3.0.
    
    The prompt is enhanced to avoid text/labels in images since Imagen
    can produce gibberish characters. Instead, we focus on visual diagrams.
    
    Args:
        prompt: The image generation prompt
        retry_count: Current retry attempt
        
    Returns:
        Image bytes if successful, None otherwise
    """
    try:
        # Authentication
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        credentials.refresh(Request())
        access_token = credentials.token
        
        # Imagen 3.0 API endpoint
        project_id = settings.GCS_PROJECT_ID
        model_id = "imagen-3.0-generate-001"
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/us-central1/publishers/google/models/{model_id}:predict"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # Enhanced prompt - explicitly avoid text/labels to prevent gibberish
        enhanced_prompt = f"""{prompt}

Style: Clean educational diagram, professional illustration, vibrant colors, high contrast.
Important: NO text, NO labels, NO letters, NO numbers, NO words in the image. Use only visual elements, icons, arrows, and symbols."""
        
        payload = {
            "instances": [{"prompt": enhanced_prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": "16:9",
                "safetyFilterLevel": "block_some",
                "personGeneration": "dont_allow"
            }
        }
        
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if "predictions" in result and len(result["predictions"]) > 0:
                        prediction = result["predictions"][0]
                        if "bytesBase64Encoded" in prediction:
                            image_bytes = base64.b64decode(prediction["bytesBase64Encoded"])
                            image_logger.info(f"✅ Image generated: {len(image_bytes)} bytes")
                            return image_bytes
                    
                    image_logger.warning(f"⚠️ No image in response")
                    return None
                    
                elif response.status == 429 and retry_count < MAX_RETRIES:
                    # Rate limited - exponential backoff
                    wait_time = RATE_LIMIT_BACKOFF_BASE * (2 ** retry_count)
                    image_logger.warning(f"⚠️ Rate limited (429), waiting {wait_time}s before retry {retry_count + 1}/{MAX_RETRIES}...")
                    await asyncio.sleep(wait_time)
                    return await generate_image_with_vertex(prompt, retry_count + 1)
                    
                else:
                    error_text = await response.text()
                    image_logger.error(f"❌ Imagen API error {response.status}: {error_text[:300]}")
                    return None
                    
    except Exception as e:
        image_logger.error(f"❌ Image generation failed: {e}")
        return None


def upload_image_to_gcs(image_bytes: bytes, slide_id: str, slide_item_id: str) -> Optional[str]:
    """
    Upload image bytes to Google Cloud Storage.
    
    Returns:
        GCS blob path (used for signed URL generation) or None on failure
        
    Note: We do NOT return public URLs as they cause CORS/ORB errors.
    The gcs_path should be used with generate_signed_url() when serving to clients.
    """
    try:
        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith('{'):
            service_account_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        else:
            with open(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI, 'r') as f:
                service_account_info = json.load(f)
        
        storage_client = storage.Client.from_service_account_info(service_account_info)
        bucket = storage_client.bucket(settings.GCS_BUCKET_NAME)
        
        gcs_path = f"slide_images/{slide_id}/{slide_item_id}.png"
        blob = bucket.blob(gcs_path)
        
        blob.upload_from_string(image_bytes, content_type="image/png")
        
        image_logger.info(f"✅ Image uploaded: {gcs_path}")
        return gcs_path
        
    except Exception as e:
        image_logger.error(f"❌ GCS upload failed: {e}")
        return None


async def update_image_status(
    image_id: str,
    status: str,
    gcs_path: Optional[str] = None
):
    """Update image record in database.
    
    Note: We store ONLY the gcs_path, not public URLs.
    Public URLs cause CORS/ORB errors in browsers.
    Signed URLs are generated on-demand when serving to clients.
    """
    db_gen = get_db()
    db = await anext(db_gen)
    try:
        if gcs_path:
            # Store gcs_path and set image_url to NULL
            # Frontend should use signed URLs from the API, not stored URLs
            await db.execute(
                text("""
                    UPDATE slide_images 
                    SET status = :status, 
                        image_url = NULL,
                        gcs_path = :gcs_path,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = CAST(:image_id AS uuid)
                """),
                {
                    "image_id": image_id,
                    "status": status,
                    "gcs_path": gcs_path
                }
            )
        else:
            await db.execute(
                text("""
                    UPDATE slide_images 
                    SET status = :status, updated_at = CURRENT_TIMESTAMP
                    WHERE id = CAST(:image_id AS uuid)
                """),
                {"image_id": image_id, "status": status}
            )
        await db.commit()
    except Exception as e:
        image_logger.error(f"❌ Failed to update image status: {e}")
        await db.rollback()
    finally:
        await db_gen.aclose()


async def process_single_image(
    image_id: str,
    slide_id: str,
    slide_item_id: str,
    prompt: str
) -> bool:
    """
    Process a single image: generate and upload.
    
    Returns:
        True if successful, False otherwise
    """
    image_logger.info(f"🎨 Generating image for: {slide_item_id}")
    
    # Update status to generating
    await update_image_status(image_id, "generating")
    
    # Generate image
    image_bytes = await generate_image_with_vertex(prompt)
    
    if image_bytes:
        # Upload to GCS - returns only gcs_path (no public URL to avoid CORS issues)
        gcs_path = upload_image_to_gcs(image_bytes, slide_id, slide_item_id)
        
        if gcs_path:
            # Store ONLY the gcs_path - signed URLs are generated on-demand when serving
            await update_image_status(image_id, "generated", gcs_path=gcs_path)
            return True
        else:
            await update_image_status(image_id, "failed")
            return False
    else:
        await update_image_status(image_id, "failed")
        return False


async def process_pending_images_for_slide(slide_id: str) -> int:
    """
    Process all pending images for a specific slide using batch processing.
    
    Returns:
        Number of images successfully generated
    """
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        # Get pending images for this slide
        result = await db.execute(
            text("""
                SELECT id, slide_item_id, prompt, style, alt_text
                FROM slide_images
                WHERE slide_id = CAST(:slide_id AS uuid)
                  AND status = 'pending'
            """),
            {"slide_id": slide_id}
        )
        rows = result.fetchall()
        
        if not rows:
            image_logger.info("No pending images to process")
            return 0
        
        image_logger.info(f"📦 Processing {len(rows)} images in batches of {BATCH_SIZE}")
        
        # Prepare image tasks
        image_tasks = []
        for row in rows:
            m = row._mapping
            image_tasks.append({
                "image_id": str(m["id"]),
                "slide_item_id": m["slide_item_id"],
                "prompt": m["prompt"]
            })
        
        # Process in batches (sequentially within each batch to avoid rate limiting)
        generated_count = 0
        total_images = len(image_tasks)
        
        for i in range(0, total_images, BATCH_SIZE):
            batch = image_tasks[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_images + BATCH_SIZE - 1) // BATCH_SIZE
            
            image_logger.info(f"🔄 Processing batch {batch_num}/{total_batches} ({len(batch)} images)")
            
            # Process images SEQUENTIALLY within batch (not parallel) to avoid rate limiting
            for j, img in enumerate(batch):
                image_num = i + j + 1
                image_logger.info(f"   📸 Image {image_num}/{total_images}: {img['slide_item_id']}")
                
                try:
                    success = await process_single_image(
                        img["image_id"],
                        slide_id,
                        img["slide_item_id"],
                        img["prompt"]
                    )
                    if success:
                        generated_count += 1
                except Exception as e:
                    image_logger.error(f"❌ Image {image_num} failed: {e}")
                
                # Delay between images within batch (except for last image in batch)
                if j < len(batch) - 1:
                    image_logger.info(f"   ⏳ Waiting {DELAY_BETWEEN_IMAGES}s before next image...")
                    await asyncio.sleep(DELAY_BETWEEN_IMAGES)
            
            # Longer delay between batches (except for last batch)
            if i + BATCH_SIZE < total_images:
                image_logger.info(f"⏳ Batch complete. Waiting {DELAY_BETWEEN_BATCHES}s before next batch...")
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)
        
        return generated_count
        
    except Exception as e:
        image_logger.error(f"❌ Error processing images: {e}")
        return 0
    finally:
        await db_gen.aclose()


async def generate_images_for_slide(slide_id: str) -> int:
    """
    Main entry point: Generate all images for a slide deck.
    
    Features:
    - Sequential batch processing to avoid rate limiting
    - Configurable delays between images and batches
    - Exponential backoff on rate limit (429) errors
    - GCS upload with path tracking for signed URLs
    
    Returns:
        Number of images successfully generated
    """
    image_logger.info(f"🖼️ Starting image generation for slide: {slide_id}")
    image_logger.info(f"   Config: batch_size={BATCH_SIZE}, delay_between_images={DELAY_BETWEEN_IMAGES}s, delay_between_batches={DELAY_BETWEEN_BATCHES}s")
    count = await process_pending_images_for_slide(slide_id)
    image_logger.info(f"✅ Image generation complete: {count} images generated")
    return count

