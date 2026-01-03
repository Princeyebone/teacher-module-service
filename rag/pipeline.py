#!/usr/bin/env python3
"""
Document processing pipeline that combines text extraction, chunking, and embedding generation.
This module provides a complete async pipeline for processing documents and storing embeddings in the database.
"""

import asyncio
import logging
import re
import sys
from typing import List, Dict, Any, Optional
from unstructured.partition.auto import partition

# Database imports
from sqlalchemy.ext.asyncio import AsyncSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Import database functions and models locally where needed to avoid circular imports
async def store_knowledge_metadata(
    db: AsyncSession, 
    file_path: str, 
    subject: str = "Unknown",
    notes: str = ""
) -> int:
    """
    Store knowledge metadata in the database with retry logic for connection timeouts.
    
    Args:
        db: Database session
        file_path: Path to the processed file
        subject: Subject of the document
        notes: Additional notes about the document
        
    Returns:
        ID of the created knowledge metadata record
    """
    # Retry logic for database connection timeouts
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Import models locally to avoid circular imports
            from model import KnowledgeMetadata
            
            knowledge_record = KnowledgeMetadata(
                teacher_id=None,
                uploader_type="system",
                subject=subject,
                level="all levels",
                region="all regions",
                pillar="cognitive science and pedagogy",
                file_path=file_path,
                source_url=None,
                license=None,
                is_embedded=False,
                embedding_model="text-embedding-005",
                chunk_count=0,
                last_indexed_at=None,
                notes=notes,
                checksum=None
            )
            
            db.add(knowledge_record)
            await db.commit()
            await db.refresh(knowledge_record)
            
            logger.info(f"Knowledge metadata stored with ID: {knowledge_record.id}")
            # After refresh, the ID should be set by the database
            if knowledge_record.id is None:
                raise RuntimeError("Failed to get ID for knowledge metadata record")
            return knowledge_record.id
            
        except Exception as e:
            retry_count += 1
            logger.warning(f"Error storing knowledge metadata (Attempt {retry_count}/{max_retries}): {str(e)}")
            await db.rollback()
            
            if retry_count >= max_retries:
                logger.error(f"Failed to store knowledge metadata after {max_retries} attempts")
                raise
            else:
                # Wait before retrying with exponential backoff
                wait_time = 2 ** retry_count
                logger.info(f"Retrying knowledge metadata storage in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

async def store_embeddings(
    db: AsyncSession, 
    knowledge_id: int, 
    chunks: List[str], 
    embeddings: List[Optional[List[float]]]
) -> None:
    """
    Store embeddings in the database in smaller batches to avoid connection timeouts.
    
    Args:
        db: Database session
        knowledge_id: ID of the knowledge metadata record
        chunks: List of text chunks
        embeddings: List of corresponding embeddings
    """
    try:
        logger.info(f"Storing {len(chunks)} embeddings in database")
        
        # Import models locally to avoid circular imports
        from model import KnowledgeEmbedding
        
        # Filter out None embeddings and their corresponding chunks
        valid_data = [(chunk, embedding, i) for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)) if embedding is not None]
        valid_chunks, valid_embeddings, valid_indices = zip(*valid_data) if valid_data else ([], [], [])
        
        logger.info(f"Found {len(valid_data)} valid embeddings to store")
        
        # If we lost a significant number of embeddings, log a warning
        failed_count = len(chunks) - len(valid_data)
        if failed_count > 0:
            logger.warning(f"⚠️ Lost {failed_count} embeddings during processing")
            if failed_count > len(chunks) * 0.2:  # More than 20% loss
                logger.warning(f"⚠️ High embedding loss rate: {failed_count}/{len(chunks)} embeddings lost")
        
        # Process embeddings in smaller batches to avoid connection timeouts
        BATCH_SIZE = 50  # Reduced batch size to prevent timeouts
        successful_embeddings = 0
        
        for i in range(0, len(valid_data), BATCH_SIZE):
            batch_data = valid_data[i:i + BATCH_SIZE]
            
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}: embeddings {i+1} to {min(i+len(batch_data), len(valid_data))}")
            
            # Retry logic for each batch
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # Check if the session is in a valid state
                    # For SQLAlchemy async sessions, we need to handle transaction state carefully
                    
                    # Store this batch of embeddings
                    batch_records = []
                    for chunk, embedding, original_index in batch_data:
                        # Sanitize chunk text before storing in database
                        sanitized_chunk = sanitize_text_for_database(chunk)
                        embedding_record = KnowledgeEmbedding(
                            knowledge_id=knowledge_id,
                            chunk_text=sanitized_chunk,
                            embedding=embedding,
                            chunk_order=original_index
                        )
                        batch_records.append(embedding_record)
                    
                    # Add all records in this batch
                    for record in batch_records:
                        db.add(record)
                    
                    # Flush this batch (don't commit yet to keep transaction open)
                    await db.flush()
                    successful_embeddings += len(batch_records)
                    logger.info(f"Successfully flushed batch {i//BATCH_SIZE + 1} with {len(batch_records)} embeddings")
                    break  # Success, break out of retry loop
                    
                except Exception as batch_error:
                    retry_count += 1
                    logger.warning(f"Error processing batch {i//BATCH_SIZE + 1} (Attempt {retry_count}/{max_retries}): {str(batch_error)}")
                    
                    # Rollback the transaction to clean up the session state
                    try:
                        await db.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"Error during rollback for batch {i//BATCH_SIZE + 1}: {rollback_error}")
                    
                    # Create a new transaction by expiring the session state
                    # This helps reset the session after a rollback
                    try:
                        # Expire all objects to force a refresh from the database
                        db.expire_all()
                    except Exception as expire_error:
                        logger.warning(f"Error during session expiration: {expire_error}")
                    
                    if retry_count >= max_retries:
                        logger.error(f"Failed to process batch {i//BATCH_SIZE + 1} after {max_retries} attempts")
                        raise batch_error
                    else:
                        # Wait before retrying
                        await asyncio.sleep(2 ** retry_count)  # Exponential backoff
        
        # Update the knowledge metadata with chunk count
        try:
            from model import KnowledgeMetadata
            knowledge_record = await db.get(KnowledgeMetadata, knowledge_id)
            if knowledge_record:
                # Store the total chunk count, not just successful embeddings
                knowledge_record.chunk_count = len(chunks)
                knowledge_record.is_embedded = True
                db.add(knowledge_record)
            
            # Commit all changes at once
            await db.commit()
            logger.info(f"Successfully stored total of {successful_embeddings} embeddings out of {len(chunks)} chunks")
        except Exception as commit_error:
            logger.error(f"Error during final commit: {commit_error}")
            await db.rollback()
            raise
    
    except Exception as e:
        # Ensure we always rollback on error to clean up session state
        try:
            await db.rollback()
        except Exception as rollback_error:
            logger.warning(f"Error during final error rollback: {rollback_error}")
        
        logger.error(f"Error storing embeddings: {str(e)}")
        raise

# Import functions from other modules
sys.path.insert(0, '..')  # Add parent directory to path
from database import get_db
from model import KnowledgeMetadata, KnowledgeEmbedding
from rag.embedding import generate_embeddings_with_gemini, generate_embedding_with_gemini
from rag.text import sanitize_text_for_database

# Import text extraction
from unstructured.partition.auto import partition
from unstructured.partition.pdf import partition_pdf

async def extract_text_elements(file_path: str) -> List[Dict[str, Any]]:
    """
    Asynchronously extracts text blocks and metadata from a document using Unstructured.io.
    Returns a list of structured blocks.
    
    Args:
        file_path: Path to the document file to process
        
    Returns:
        List of dictionaries containing text blocks with 'text', 'type', and 'metadata' keys
    """
    try:
        logger.info(f"Starting async extraction for file: {file_path}")
        
        # Determine file type and use appropriate extraction method with UTF-8 encoding
        import os
        _, file_extension = os.path.splitext(file_path)
        
        if file_extension.lower() == '.pdf':
            # Use PDF-specific extraction with UTF-8 encoding
            from unstructured.partition.pdf import partition_pdf
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: partition_pdf(file_path, encoding="utf-8")
            )
        else:
            # Use generic partition function for other file types
            loop = asyncio.get_event_loop()
            elements = await loop.run_in_executor(None, partition, file_path)
        
        text_blocks = []
        for el in elements:
            if hasattr(el, 'text') and el.text.strip():
                # Clean the text to handle encoding issues
                text = el.text.strip()
                
                # Fix common encoding issues
                text = text.replace('\x00', '')  # Remove null characters
                text = text.replace('ΓÇó', '•')  # Fix bullet points
                text = text.replace('ΓÇô', '-')  # Fix em dashes
                text = text.replace('ΓÇÖ', "'")  # Fix apostrophes
                text = text.replace('ΓÇô', '"')  # Fix quotes
                text = text.replace('ΓÇ¥', '—')  # Fix em dashes
                text = text.replace('knowJedp', 'knowledge')  # Fix specific corruption
                
                # Additional encoding fix for Latin-1 to UTF-8 issues
                try:
                    # If text contains Latin-1 encoded characters, decode them properly
                    if any(ord(c) > 127 for c in text):
                        text = text.encode('latin1').decode('utf-8', errors='ignore')
                except (UnicodeEncodeError, UnicodeDecodeError):
                    # If encoding fix fails, keep original text
                    pass
                
                # Only add if text has meaningful content after cleaning
                if text.strip():
                    text_blocks.append({
                        "text": text.strip(),
                        "type": getattr(el, 'category', 'text'),
                        "metadata": getattr(el, 'metadata', {})
                    })
        
        logger.info(f"Async extraction completed. Found {len(text_blocks)} text blocks.")
        return text_blocks
    
    except Exception as e:
        logger.error(f"Error during async text extraction: {str(e)}")
        raise

async def chunk_text_blocks(text_blocks: List[Dict[str, Any]], max_tokens: int = 700) -> List[str]:
    """
    Asynchronously combine text blocks into coherent chunks based on structure and size.
    Improved version for academic documents.
    
    Args:
        text_blocks: List of text blocks with 'text' and 'type' keys
        max_tokens: Maximum number of tokens per chunk (approximate)
        
    Returns:
        List of chunked text strings
    """
    try:
        logger.info(f"Starting async chunking process for {len(text_blocks)} text blocks")
        
        # Run the CPU-intensive chunking operation in a thread pool
        loop = asyncio.get_event_loop()
        chunks = await loop.run_in_executor(None, _chunk_text_blocks_internal, text_blocks, max_tokens)
        
        logger.info(f"Async chunking completed. Created {len(chunks)} chunks")
        return chunks
    
    except Exception as e:
        logger.error(f"Error during async chunking: {str(e)}")
        raise

def _chunk_text_blocks_internal(text_blocks: List[Dict[str, Any]], max_tokens: int = 700) -> List[str]:
    """
    Internal chunking implementation run in a thread pool.
    Uses a hybrid approach combining custom logic with LangChain's semantic chunking.
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        # Combine all text blocks into a single text with structural markers
        combined_text = ""
        for block in text_blocks:
            text = block.get("text", "")
            block_type = block.get("type", "text")
            
            # Add structural context based on block type
            if block_type in ["Title", "Header"]:
                combined_text += f"\n\n# {text}\n\n"
            elif block_type == "Section":
                combined_text += f"\n\n## {text}\n\n"
            elif block_type == "ListItem":
                combined_text += f"\n- {text}"
            else:
                combined_text += f" {text}"
        
        # Use LangChain's RecursiveCharacterTextSplitter for semantic chunking
        try:
            from tiktoken import get_encoding
            encoding = get_encoding("cl100k_base")
            length_function = lambda text: len(encoding.encode(text))
        except ImportError:
            # Fallback to character length if tiktoken is not available
            length_function = len
            logger.warning("tiktoken not available, falling back to character length estimation")
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tokens,
            chunk_overlap=max_tokens // 10,  # 10% overlap
            length_function=length_function,
            separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""]
        )
        
        chunks = text_splitter.split_text(combined_text.strip())
        
        # Filter out very short chunks
        filtered_chunks = [chunk.strip() for chunk in chunks if len(chunk.strip().split()) >= 10]
        
        logger.info(f"Created {len(filtered_chunks)} filtered chunks from {len(chunks)} raw chunks")
        return filtered_chunks
        
    except ImportError:
        logger.warning("LangChain not available, using basic chunking")
        # Fallback to basic chunking if LangChain is not available
        combined_text = " ".join([block.get("text", "") for block in text_blocks])
        
        # Simple chunking by sentences
        import re
        sentences = re.split(r'[.!?]+', combined_text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < max_tokens * 4:  # Approximate token to char ratio
                current_chunk += sentence + ". "
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
            
        return chunks
    except Exception as e:
        logger.error(f"Error during internal chunking: {str(e)}")
        # Return the combined text as a single chunk if all else fails
        combined_text = " ".join([block.get("text", "") for block in text_blocks])
        return [combined_text.strip()] if combined_text.strip() else []

async def generate_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """
    Generate embeddings for a list of texts using the configured embedding model.
    
    Args:
        texts: List of texts to generate embeddings for
        
    Returns:
        List of embedding vectors (or None for failed embeddings)
    """
    try:
        logger.info(f"Generating embeddings for {len(texts)} texts")
        
        # Use the embedding module's function
        from rag.embedding import generate_embeddings_with_gemini
        embeddings = generate_embeddings_with_gemini(texts)
        
        logger.info(f"Generated embeddings for {len([e for e in embeddings if e is not None])}/{len(texts)} texts")
        return embeddings
        
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        # Return a list of None values to indicate failure for all texts
        return [None] * len(texts)

async def process_document(
    file_path: str,
    subject: str = "Unknown",
    notes: str = "",
    store_in_db: bool = True
) -> Dict[str, Any]:
    """
    Complete document processing pipeline.
    
    Steps:
    1. Extract text elements using Unstructured.io
    2. Chunk text blocks into coherent segments
    3. Generate embeddings for each chunk
    4. Store results in database
    
    Args:
        file_path: Path to the document file
        subject: Subject of the document
        notes: Additional notes about the document
        store_in_db: Whether to store results in database
        
    Returns:
        Dictionary containing processing results
    """
    logger.info(f"Starting document processing pipeline for: {file_path}")
    
    try:
        # Step 1: Extract text elements
        text_blocks = await extract_text_elements(file_path)
        logger.info(f"✓ Extraction: {len(text_blocks)} text blocks")
        
        # Step 2: Chunk text blocks
        chunks = await chunk_text_blocks(text_blocks)
        logger.info(f"✓ Chunking: {len(chunks)} chunks")
        
        # Step 3: Generate embeddings
        logger.info("Generating embeddings...")
        embeddings = await generate_embeddings(chunks)
        logger.info(f"✓ Embeddings: {len([e for e in embeddings if e is not None])} generated")
        
        result = {
            "file_path": file_path,
            "subject": subject,
            "chunks_count": len(chunks),
            "embeddings_count": len([e for e in embeddings if e is not None]),
            "chunks": chunks,
            "embeddings": embeddings
        }
        
        # Step 4: Store in database
        if store_in_db:
            db_gen = get_db()
            db = await db_gen.__anext__()
            
            try:
                knowledge_id = await store_knowledge_metadata(db, file_path, subject, notes)
                result["knowledge_id"] = knowledge_id
                
                await store_embeddings(db, knowledge_id, chunks, embeddings)
                result["stored_in_db"] = True
                
                logger.info(f"✓ Database storage: knowledge_id={knowledge_id}")
            finally:
                await db_gen.aclose()
        else:
            result["stored_in_db"] = False
        
        logger.info("✅ Document processing pipeline completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"❌ Pipeline error: {str(e)}")
        raise