# RAG Background Processing System

This module provides background task processing for RAG (Retrieval-Augmented Generation) file uploads, including intelligent text extraction using PyMuPDF with OCR fallback and AI-powered embedding generation.

## Components

### 1. Background Task (`rag_back.py`)
- Text extraction using PyMuPDF with OCR fallback
- Document chunking and embedding generation
- Database storage of knowledge metadata and embeddings
- WebSocket notifications to teachers

### 2. ARQ Worker (`arq_worker.py`)
- Worker configuration and startup scripts
- CLI commands for testing and management

### 3. Enqueue Helper (`enqueue_rag.py`)
- Function to enqueue RAG processing tasks
- Integration with the ARQ task queue

### 4. File Handler (`file_handler/rag_file_handler.py`)
- REST API endpoint for file uploads
- Initial metadata storage
- Task queuing for background processing

## Usage

### Starting the Worker

```bash
# Start the RAG processing worker
python rag_back/arq_worker.py start

# Or using ARQ directly
python -m arq rag_back.arq_worker
```

### Testing the Worker

```bash
# Test Redis connection
python rag_back/arq_worker.py test

# Show configuration info
python rag_back/arq_worker.py info

# Enqueue a test task
python rag_back/arq_worker.py enqueue
```

### API Endpoint

The RAG file upload endpoint is available at:
```
POST /api/teacher/rag/upload
```

Form parameters:
- `file` (required): The file to process
- `subject` (required): Subject of the document
- `notes` (optional): Notes about the document
- `level` (required): Educational level
- `region` (required): Geographic region
- `source_url` (optional): Source URL of the document
- `file_path_field` (optional): File path in storage
- `pillar` (required): Knowledge pillar (curriculum, cognitive, assessment, pedagogy, misc)

## Task Flow

1. Teacher uploads a file via the API endpoint
2. File is saved locally and a signed URL is generated for GCS upload
3. Initial KnowledgeMetadata record is created in the database
4. RAG processing task is enqueued in the `rag_queue`
5. Background worker processes the file:
   - Extracts text using PyMuPDF with OCR fallback
   - Chunks the text into meaningful segments
   - Generates embeddings using Vertex AI
   - Stores chunks and embeddings in the database
   - Updates KnowledgeMetadata record with processing results
6. WebSocket notifications are sent to the teacher at each step
7. Teacher receives completion notification with results

## WebSocket Notifications

The system sends real-time updates to teachers via WebSocket:

- `status: "uploaded"` - File uploaded successfully
- `status: "processing"` - RAG processing started
- `status: "completed"` - Processing completed successfully
- `status: "error"` - Processing failed with error details

## Supported File Types

- PDF (with PyMuPDF and OCR fallback)
- Images (JPG, PNG, BMP, TIFF) with OCR
- Documents (DOCX, XLSX, XLS)
- Plain text (TXT)

## Configuration

The worker can be configured through the `worker_config` dictionary in `rag_back.py`:

- `max_tries`: 3 (retry failed jobs 3 times)
- `retry_delay`: 30 (wait 30 seconds between retries)
- `job_timeout`: 600 (10 minutes max per job)
- `concurrent_jobs`: 1 (process 1 job simultaneously per worker)
- `keep_result`: 3600 (keep job results for 1 hour)