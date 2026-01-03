import os
import json
import time
import logging
import sys
import traceback
from typing import List, Optional, Sequence
import concurrent.futures

# Configure logging to show in terminal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Add the parent directory to the path so we can import config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import your settings if available
try:
    from config import settings  # assuming you already load this globally
    CONFIG_AVAILABLE = True
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Config not available: {e}")
    CONFIG_AVAILABLE = False
    # Create a mock settings object for testing
    class MockSettings:
        GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI = os.environ.get('GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI', '')
        GCS_PROJECT_ID = os.environ.get('GCS_PROJECT_ID', 'test-project')
        GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    
    settings = MockSettings()

logger = logging.getLogger(__name__)

# Try to import Vertex AI components
try:
    import json
    import time
    import google.auth.transport.requests
    from google.oauth2 import service_account
    from vertexai.preview import generative_models
    import vertexai
    from vertexai.preview.language_models import TextEmbeddingModel  # ✅ updated import path
    from typing import List, Optional, Sequence

    # Store credentials globally so we can refresh them
    global_credentials = None
    global_scoped_credentials = None
    model = None

    # 1️⃣ Load service account credentials directly from settings
    if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith("{"):
        credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
        global_credentials = service_account.Credentials.from_service_account_info(credentials_info)
    else:
        global_credentials = service_account.Credentials.from_service_account_file(
            settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
        )

    # 2️⃣ Add the correct scopes for Vertex AI
    global_scoped_credentials = global_credentials.with_scopes([
        "https://www.googleapis.com/auth/cloud-platform"
    ])

    # 3️⃣ Initialize Vertex AI client with the credentials
    vertexai.init(project=settings.GCS_PROJECT_ID, location="us-central1", credentials=global_scoped_credentials)

    # 4️⃣ Load the Gemini embedding model
    logger.info("Initializing Vertex AI embedding model: gemini-embedding-001")
    
    # Add retry logic for model initialization
    model_init_retries = 3
    model_init_attempt = 0
    model = None
    
    while model_init_attempt < model_init_retries:
        try:
            model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
            logger.info("✅ Vertex AI Gemini model initialized successfully")
            break
        except Exception as e:
            model_init_attempt += 1
            logger.error(f"❌ Failed to initialize Vertex AI Gemini model (Attempt {model_init_attempt}/{model_init_retries}): {e}")
            
            if model_init_attempt < model_init_retries:
                # Wait before retrying
                wait_time = 5 * model_init_attempt
                logger.info(f"Retrying model initialization in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error("❌ Max retry attempts reached for model initialization")
                model = None

    def _refresh_credentials():
        """
        Refresh the Google Cloud credentials if they're expired.
        """
        global global_credentials, global_scoped_credentials
        
        try:
            logger.info("Refreshing Google Cloud credentials...")
            # Refresh the credentials
            if global_credentials is not None:
                # For service account credentials, we need to refresh differently
                # Service account credentials don't have a refresh method in the same way
                # Instead, we should recreate the credentials with the same info
                try:
                    # Try to refresh first
                    request = google.auth.transport.requests.Request()
                    if hasattr(global_credentials, 'refresh'):
                        global_credentials.refresh(request)
                        logger.info("Credentials refreshed using refresh method")
                    else:
                        # If no refresh method, recreate credentials
                        logger.info("Recreating credentials as refresh method not available")
                        if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith("{"):
                            credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
                            global_credentials = service_account.Credentials.from_service_account_info(credentials_info)
                        else:
                            global_credentials = service_account.Credentials.from_service_account_file(
                                settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
                            )
                        
                except Exception as refresh_error:
                    logger.warning(f"Direct refresh failed, recreating credentials: {refresh_error}")
                    # Recreate credentials as fallback
                    if settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI.startswith("{"):
                        credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI)
                        global_credentials = service_account.Credentials.from_service_account_info(credentials_info)
                    else:
                        global_credentials = service_account.Credentials.from_service_account_file(
                            settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI
                        )
                
                # Apply scopes
                global_scoped_credentials = global_credentials.with_scopes([
                    "https://www.googleapis.com/auth/cloud-platform"
                ])
                
                # Re-initialize Vertex AI with refreshed credentials
                vertexai.init(project=settings.GCS_PROJECT_ID, location="us-central1", credentials=global_scoped_credentials)
                logger.info("✅ Google Cloud credentials refreshed successfully")
                return True
            else:
                logger.error("❌ No credentials available to refresh")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to refresh credentials: {e}")
            return False

    # You can set your desired dimensionality: 768, 1536, or 3072
    DEFAULT_DIMENSIONALITY = 1536

    def generate_embedding_with_gemini(
        text: str,
        output_dimensionality: int = DEFAULT_DIMENSIONALITY,
        max_retries: int = 5
    ) -> Optional[List[float]]:
        """
        Generate embeddings for text using Vertex AI Gemini Embeddings.

        Args:
            text: Text to generate embedding for
            output_dimensionality: Desired output dimension (768, 1536, or 3072)
            max_retries: Retry attempts for transient errors (e.g., rate limits)

        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        return generate_embeddings_with_gemini([text], output_dimensionality, max_retries)[0] if generate_embeddings_with_gemini([text], output_dimensionality, max_retries) else None

    def generate_embeddings_with_gemini(
        texts: Sequence[str],
        output_dimensionality: int = DEFAULT_DIMENSIONALITY,
        max_retries: int = 5
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts using Vertex AI Gemini Embeddings in batch.
        Respects the API limit of 250 instances per batch.
        
        Args:
            texts: List of texts to generate embeddings for
            output_dimensionality: Desired output dimension (768, 1536, or 3072)
            max_retries: Retry attempts for transient errors (e.g., rate limits)
            
        Returns:
            List of embedding vectors (or None for failed embeddings)
        """
        # Vertex AI has a limit of 250 instances per batch
        # Reduced to 100 to be more conservative with quota limits
        MAX_BATCH_SIZE = 100
        all_embeddings = []
        
        logger.info(f"Starting batch processing of {len(texts)} texts in batches of {MAX_BATCH_SIZE}")
        total_batches = (len(texts) - 1) // MAX_BATCH_SIZE + 1
        logger.info(f"Total batches to process: {total_batches}")
        
        # Log the first few texts being sent for debugging
        logger.info(f"First 3 texts being processed: {[text[:100] + '...' if len(text) > 100 else text for text in texts[:3]]}")
        
        # Process texts in batches
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch_number = i // MAX_BATCH_SIZE + 1
            batch_texts = texts[i:i + MAX_BATCH_SIZE]
            logger.info(f"Processing batch {batch_number}/{total_batches} with {len(batch_texts)} texts")
            
            # Log batch details for debugging
            logger.info(f"Batch {batch_number} details:")
            logger.info(f"  - Text count: {len(batch_texts)}")
            logger.info(f"  - First text preview: {batch_texts[0][:100] + '...' if batch_texts and len(batch_texts[0]) > 100 else batch_texts[0] if batch_texts else 'None'}")
            logger.info(f"  - Output dimensionality: {output_dimensionality}")
            
            batch_embeddings = _generate_embeddings_batch(batch_texts, output_dimensionality, max_retries)
            all_embeddings.extend(batch_embeddings)
            
            # Add a small delay between batches to help with rate limiting
            if i + MAX_BATCH_SIZE < len(texts):
                logger.info("Pausing briefly between batches to help with rate limiting...")
                time.sleep(1)
            
        logger.info(f"Completed batch processing. Total embeddings generated: {len(all_embeddings)}")
        return all_embeddings

    def _generate_embeddings_batch(
        texts: Sequence[str],
        output_dimensionality: int = DEFAULT_DIMENSIONALITY,
        max_retries: int = 5
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for a batch of texts (up to 250).
        
        Args:
            texts: List of texts to generate embeddings for (max 250)
            output_dimensionality: Desired output dimension (768, 1536, or 3072)
            max_retries: Retry attempts for transient errors (e.g., rate limits)
            
        Returns:
            List of embedding vectors (or None for failed embeddings)
        """
        attempt = 0
        while attempt < max_retries:
            try:
                global model
                logger.info(f"Generating embeddings for batch of {len(texts)} texts...")
                logger.info(f"Output dimensionality: {output_dimensionality}")
                
                # ✅ Generate embeddings using Gemini Embedding model in batch
                if model is not None:
                    # Log the exact texts being sent to the API
                    logger.info(f"Sending {len(texts)} texts to Vertex AI API")
                    for idx, text in enumerate(texts[:3]):  # Log first 3 texts
                        logger.info(f"Text {idx+1}: {text[:100] + '...' if len(text) > 100 else text}")
                    
                    # Add detailed logging and timeout
                    logger.info("Calling model.get_embeddings with timeout...")
                    try:
                        import concurrent.futures
                        import functools
                        
                        # Create a partial function with the arguments
                        embedding_func = functools.partial(
                            model.get_embeddings,
                            texts,  # type: ignore
                            output_dimensionality=output_dimensionality
                        )
                        
                        # Use a thread pool executor with timeout
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(embedding_func)
                            # Set a reasonable timeout (100 seconds per 100 texts, max 10 minutes)
                            timeout = max(100, min(600, len(texts) * 1.0))
                            logger.info(f"Using timeout of {timeout} seconds for {len(texts)} texts")
                            embeddings = future.result(timeout=timeout)
                        
                        logger.info("✅ model.get_embeddings call completed successfully")
                    except concurrent.futures.TimeoutError as timeout_error:
                        logger.error(f"Timeout error calling model.get_embeddings after {timeout} seconds: {timeout_error}")
                        raise
                    except Exception as e:
                        logger.error(f"Error calling model.get_embeddings: {e}")
                        logger.error(f"Error type: {type(e)}")
                        logger.error(f"Error traceback: {traceback.format_exc()}")
                        raise
                else:
                    logger.error("❌ Model is not initialized. Cannot generate embeddings.")
                    # Try to re-initialize the model
                    logger.info("Attempting to re-initialize the model...")
                    try:
                        model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
                        logger.info("✅ Vertex AI Gemini model re-initialized successfully")
                        # Retry the embedding generation
                        embeddings = model.get_embeddings(
                            texts,  # type: ignore
                            output_dimensionality=output_dimensionality
                        )
                    except Exception as reinit_error:
                        logger.error(f"❌ Failed to re-initialize Vertex AI Gemini model: {reinit_error}")
                        return [None] * len(texts)

                if embeddings:
                    result = []
                    logger.info(f"Processing {len(embeddings)} embeddings returned from API")
                    for i, embedding in enumerate(embeddings):
                        if embedding and hasattr(embedding, 'values'):
                            embedding_vector = embedding.values
                            logger.info(f"✅ Successfully generated embedding {i+1}/{len(texts)} with length: {len(embedding_vector)}")
                            result.append(embedding_vector)
                        else:
                            logger.warning(f"⚠️ No embedding returned for text {i+1}/{len(texts)}")
                            result.append(None)
                    logger.info(f"✅ Batch processing completed. Generated {len([r for r in result if r is not None])} successful embeddings")
                    return result
                else:
                    logger.warning("⚠️ No embeddings returned from Vertex AI")
                    return [None] * len(texts)

            except Exception as e:
                error_str = str(e)
                logger.error(f"❌ Error generating embeddings: {error_str}")
                logger.error(f"Error type: {type(e)}")
                logger.error(f"Full traceback: {traceback.format_exc()}")

                # Handle authentication errors - these require different handling than retries
                if "401" in error_str or "invalid authentication credentials" in error_str.lower() or "access_token_expired" in error_str.lower():
                    logger.error("❌ Authentication error - credentials are invalid or expired")
                    # Try to refresh credentials
                    if _refresh_credentials():
                        # Retry with refreshed credentials (only once)
                        logger.info("Retrying with refreshed credentials...")
                        try:
                            # Re-initialize Vertex AI with refreshed credentials
                            vertexai.init(project=settings.GCS_PROJECT_ID, location="us-central1", credentials=global_scoped_credentials)
                            
                            # Re-initialize the model with refreshed credentials
                            try:
                                model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
                                logger.info("✅ Vertex AI Gemini model re-initialized successfully")
                                
                                # Retry the embedding generation
                                embeddings = model.get_embeddings(
                                    texts,  # type: ignore
                                    output_dimensionality=output_dimensionality
                                )
                                
                                logger.info(f"✅ Successfully generated embeddings after credential refresh")
                                # Process the embeddings as normal
                                result = []
                                for i, embedding in enumerate(embeddings):
                                    if embedding and hasattr(embedding, 'values'):
                                        embedding_vector = embedding.values
                                        logger.info(f"✅ Successfully generated embedding {i+1}/{len(texts)} with length: {len(embedding_vector)}")
                                        result.append(embedding_vector)
                                    else:
                                        logger.warning(f"⚠️ No embedding returned for text {i+1}/{len(texts)}")
                                        result.append(None)
                                return result
                            except Exception as model_error:
                                logger.error(f"❌ Failed to re-initialize Vertex AI Gemini model: {model_error}")
                                return [None] * len(texts)
                        except Exception as retry_error:
                            logger.error(f"❌ Failed to generate embeddings even after credential refresh: {retry_error}")
                    else:
                        logger.error("Please check your Google Cloud credentials and refresh them if necessary")
                    
                    # Don't retry authentication errors as they won't be fixed by waiting
                    return [None] * len(texts)
                
                # Handle rate limit (HTTP 429) gracefully with exponential backoff
                elif "429" in error_str or "quota" in error_str.lower():
                    attempt += 1
                    wait_time = 10 * attempt
                    logger.warning(f"⚠️ Quota/rate limit hit. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                    time.sleep(wait_time)
                
                # Handle Service Unavailable (503) and connection errors with more robust retry logic
                elif "503" in error_str or "unavailable" in error_str.lower() or "failed to connect" in error_str.lower() or "socket is null" in error_str.lower():
                    attempt += 1
                    if attempt < max_retries:
                        # Exponential backoff with longer delays for connection issues
                        wait_time = min(30 * (2 ** attempt), 300)  # Max 5 minutes
                        logger.warning(f"⚠️ Service unavailable or connection error. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                        
                        # Try to refresh credentials and reinitialize model for connection issues
                        logger.info("Attempting to refresh credentials and reinitialize model for connection issue...")
                        try:
                            # Refresh credentials
                            if _refresh_credentials():
                                # Re-initialize Vertex AI with refreshed credentials
                                vertexai.init(project=settings.GCS_PROJECT_ID, location="us-central1", credentials=global_scoped_credentials)
                                
                                # Re-initialize the model
                                model = TextEmbeddingModel.from_pretrained("gemini-embedding-001")
                                logger.info("✅ Vertex AI Gemini model re-initialized successfully after connection issue")
                        except Exception as reinit_error:
                            logger.error(f"Failed to reinitialize after connection issue: {reinit_error}")
                        
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Max retry attempts reached for service unavailable error. Returning None for all texts.")
                        return [None] * len(texts)
                
                elif "batchSize" in error_str and "251" in error_str:
                    # Handle batch size limit error
                    logger.error("❌ Batch size limit exceeded. This should not happen as we're already chunking.")
                    return [None] * len(texts)
                else:
                    # For other errors, increment attempt counter and retry
                    attempt += 1
                    if attempt < max_retries:
                        wait_time = 5 * attempt
                        logger.warning(f"⚠️ Unexpected error. Retrying in {wait_time}s... (Attempt {attempt}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"❌ Max retry attempts reached for this batch. Returning None for all texts.")
                        return [None] * len(texts)
        
        logger.error("❌ Max retry attempts reached. Embedding generation failed.")
        return [None] * len(texts)

except ImportError as e:
    logger.warning(f"Vertex AI components not available: {e}")
    model = None


# 🧪 Test function
def test_embedding():
    """Test the embedding generation"""
    text = "Education is the most powerful weapon which you can use to change the world."
    embedding = generate_embedding_with_gemini(text)

    if embedding:
        print("✅ Embedding length:", len(embedding))
        print("🔢 Sample of embedding vector:", embedding[:10])
    else:
        print("❌ Failed to generate embedding")


async def process_embedding_task(ctx: dict, teacher_id: str, knowledge_id: int, chunks: List[str], metadata: dict):
    """
    ARQ background task for processing embedding generation.
    
    Args:
        ctx: ARQ context
        teacher_id: UUID string of the teacher
        knowledge_id: ID of the KnowledgeMetadata record
        chunks: List of text chunks to generate embeddings for
        metadata: Dictionary containing subject, notes, etc.
    """
    import asyncio
    import logging
    import traceback
    from uuid import UUID
    from datetime import datetime
    
    # Import database functions
    try:
        from database import get_db
        from model import KnowledgeMetadata, KnowledgeEmbedding
        from sqlalchemy import select, update
        from rag.text import sanitize_text_for_database  # Import sanitization function
    except ImportError as e:
        logger.error(f"Failed to import database functions: {e}")
        raise
    
    # Import WebSocket publishing function
    try:
        from sch_ground.background import publish_ws_message, save_notification
    except ImportError as e:
        logger.error(f"Failed to import WebSocket functions: {e}")
        raise
    
    logger.info(f"🚀 Starting embedding generation task for teacher {teacher_id}")
    logger.info(f"📚 Knowledge ID: {knowledge_id}")
    logger.info(f"🧩 Chunks: {len(chunks)}")
    logger.info(f"📝 Metadata: {metadata}")
    
    # Log the first few chunks for debugging
    if chunks:
        logger.info(f"First chunk preview: {chunks[0][:100]}...")
    
    try:
        # Send initial status update via WebSocket
        await publish_ws_message(teacher_id, {
            "status": "processing",
            "message": f"Starting embedding generation for {metadata.get('notes', 'document')}",
            "knowledge_id": knowledge_id,
            "task_type": "embedding_generation"
        })
        
        # Extract metadata fields
        subject = metadata.get("subject", "Unknown")
        notes = metadata.get("notes", "")
        level = metadata.get("level", "all levels")
        region = metadata.get("region", "all regions")
        pillar = metadata.get("pillar", "misc")
        
        logger.info(f"📝 Processing document: {notes}")
        
        # Validate inputs
        if not chunks or not isinstance(chunks, list):
            raise ValueError("Invalid chunks provided")
        
        if len(chunks) == 0:
            raise ValueError("No chunks provided for embedding generation")
        
        # Step 1: Generate embeddings for all chunks
        logger.info("🧠 Generating embeddings for chunks...")
        embeddings = generate_embeddings_with_gemini(chunks)
        
        if not embeddings:
            raise RuntimeError("Failed to generate embeddings")
        
        successful_embeddings = [emb for emb in embeddings if emb is not None]
        logger.info(f"✅ Generated embeddings for {len(successful_embeddings)}/{len(chunks)} chunks")
        
        # Step 2: Store embeddings in KnowledgeEmbedding table
        logger.info("💾 Storing embeddings in KnowledgeEmbedding table...")
        db_gen = get_db()
        db = await db_gen.__anext__()
        
        try:
            # Create KnowledgeEmbedding records for each successful embedding
            embedding_records = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                if embedding is not None:
                    # Sanitize chunk text before storing in database
                    sanitized_chunk = sanitize_text_for_database(chunk)
                    embedding_record = KnowledgeEmbedding(
                        knowledge_id=knowledge_id,
                        chunk_text=sanitized_chunk,
                        embedding=embedding,
                        chunk_order=i,
                        subject=subject,
                        level=level,
                        region=region,
                        pillar=pillar
                    )
                    embedding_records.append(embedding_record)
            
            # Bulk insert embedding records
            db.add_all(embedding_records)
            await db.commit()
            
            for record in embedding_records:
                await db.refresh(record)
            
            logger.info(f"✅ Stored {len(embedding_records)} embedding records in database")
            
            # Step 3: Update KnowledgeMetadata record
            logger.info("🔄 Updating KnowledgeMetadata record...")
            stmt = update(KnowledgeMetadata).where(KnowledgeMetadata.id == knowledge_id).values(
                is_embedded=True,
                embedding_model="gemini-embedding-001",
                chunk_count=len(chunks),
                last_indexed_at=datetime.utcnow()
            )
            await db.execute(stmt)
            await db.commit()
            
            logger.info("✅ KnowledgeMetadata record updated successfully")
            
        except Exception as db_error:
            logger.error(f"❌ Database error: {db_error}")
            await db.rollback()
            raise
        finally:
            await db_gen.aclose()
        
        # Send success notification via WebSocket
        await publish_ws_message(teacher_id, {
            "status": "completed",
            "message": f"Embedding generation completed successfully for {notes}",
            "knowledge_id": knowledge_id,
            "embeddings_count": len(successful_embeddings),
            "task_type": "embedding_generation"
        })
        
        # Save success notification
        await save_notification(
            teacher_id=teacher_id,
            title="Embedding Generation Completed",
            message=f"Successfully generated embeddings for {notes} with {len(successful_embeddings)} vectors",
            type_="success"
        )
        
        return {
            "status": "success",
            "knowledge_id": knowledge_id,
            "embeddings_count": len(successful_embeddings),
            "message": "Embedding generation completed successfully"
        }
        
    except Exception as e:
        error_msg = f"Embedding generation failed for knowledge ID {knowledge_id}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        logger.error(traceback.format_exc())
        
        # Send error notification via WebSocket
        await publish_ws_message(teacher_id, {
            "status": "error",
            "message": f"Embedding generation failed: {str(e)}",
            "knowledge_id": knowledge_id,
            "error": str(e),
            "task_type": "embedding_generation"
        })
        
        # Save error notification
        await save_notification(
            teacher_id=teacher_id,
            title="Embedding Generation Failed",
            message=f"Failed to generate embeddings for knowledge ID {knowledge_id}: {str(e)}",
            type_="error"
        )
        
        raise RuntimeError(error_msg)


if __name__ == "__main__":
    test_embedding()