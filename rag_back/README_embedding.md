# Embedding Generation Background Workers

This directory contains the implementation for background processing of embedding generation tasks using ARQ workers.

## Overview

The embedding workers are designed to process text chunks and generate embeddings using Vertex AI Gemini Embeddings, following the exact implementation from `batch2_rag.py`.

## Components

### 1. `embedding_worker.py`
- Contains the main embedding processing task function
- Defines worker configuration for single worker
- Implements embedding generation using `generate_embeddings_with_gemini`
- Handles database storage of embeddings

### 2. `embedding_worker.py` (executable script)
- Worker script that can be run directly
- Processes tasks from the single queue
- Handles one job at a time for resource management

### 3. `run_embedding_workers.py`
- Runner script to start the embedding worker
- Provides commands for testing, info, and enqueueing test tasks

### 4. `enqueue_embedding.py`
- Functions to enqueue embedding tasks
- Both async and sync versions available

### 5. `embedding_back.py`
- Main interface for text processing and embedding generation
- Extracts text, chunks it, stores in database, and enqueues embedding tasks

### 6. `test_embedding_processing.py`
- Test script to verify functionality

## Usage

### Starting the Worker

```bash
# Start the embedding worker
python run_embedding_workers.py

# Or start directly
python embedding_worker.py
```

### Enqueueing Tasks

```python
from rag_back.enqueue_embedding import enqueue_embedding_sync

job_id = enqueue_embedding_sync(
    teacher_id="teacher-uuid",
    knowledge_id=123,
    chunks=["chunk1", "chunk2", "chunk3"],
    metadata={
        "subject": "Mathematics",
        "notes": "Algebra basics"
    }
)
```

### Processing Text for Embedding

```python
from rag_back.embedding_back import process_text_for_embedding_sync

result = process_text_for_embedding_sync(
    teacher_id="teacher-uuid",
    file_path="/path/to/document.pdf",
    subject="Mathematics",
    notes="Algebra basics"
)
```

## Worker Configuration

- **One worker** for embedding generation
- **One job per worker** at a time to manage resource usage
- **15-minute job timeout** for long-running embedding tasks
- **Single Redis queue**: `embedding_queue`

## Event-Driven Architecture

The system is now event-driven:
1. Text chunking workers process documents and automatically enqueue embedding tasks
2. Embedding worker processes embedding generation tasks from the queue
3. WebSocket notifications provide real-time status updates

## Architecture

```
[Text Processing] → [Chunking] → [TestText Storage] → [KnowledgeMetadata Creation] 
                                    ↓
                            [Embedding Task Enqueue]
                                    ↓
                              [Embedding Worker]
                                (embedding_queue)
```

## Requirements

- Redis server running on localhost:6379
- Google Cloud credentials configured for Vertex AI
- Required Python packages installed