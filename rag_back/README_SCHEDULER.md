# RAG Processing Scheduler

## Overview

The RAG Processing Scheduler is a background task that monitors newly created KnowledgeMetadata entries and automatically schedules RAG processing (text extraction, chunking, and embedding) 120 seconds after file upload.

## How It Works

1. **User uploads file** via curriculum or semester plan upload endpoint
2. **KnowledgeMetadata entry is created** in the database
3. **Scheduler detects new entries** by periodically scanning the database
4. **After 120 seconds**, it downloads the file from GCS to local storage
5. **Enqueues the text extraction task** which automatically chains to chunking and embedding

## Flow Diagram

```
User Upload
     ↓
KnowledgeMetadata Entry Created
     ↓
RAG Scheduler Detects Entry (every 30s)
     ↓
Wait 120 seconds after creation
     ↓
Download file from GCS → Local Storage
     ↓
Enqueue Text Extraction Task
     ↓
Automatic Chaining: Text Extraction → Chunking → Embedding
     ↓
Results Stored in KnowledgeEmbedding Table
```

## Running the Scheduler

### For All Teachers (Default Behavior)
To run the RAG processing scheduler for all teachers:

```bash
python rag_back/schedule_rag_processing.py
```

### For Specific Teacher Only
To run the scheduler for a specific teacher only:

```bash
python rag_back/schedule_rag_processing.py --teacher-id <teacher_uuid>
```

Example:
```bash
python rag_back/schedule_rag_processing.py --teacher-id 123e4567-e89b-12d3-a456-426614174000
```

## Prerequisites

- Redis server running (for ARQ task queue)
- Google Cloud Storage configured
- Database access configured
- All required Python dependencies installed

## Configuration

The scheduler uses the same configuration as the main application:
- Database connection from `config.py`
- GCS settings from `config.py`
- Redis settings from `rag_back/text_chunking_worker.py`

## Monitoring

The scheduler logs all activities to:
- Console output
- `rag_scheduler.log` file

Log levels:
- INFO: Normal operations
- WARNING: Non-critical issues
- ERROR: Critical failures

## Error Handling

- Failed downloads are retried
- Failed task enqueuing is logged but doesn't stop the scheduler
- Duplicate processing is prevented by tracking processed entries

## Performance

- Checks for new entries every 30 seconds
- Processes multiple entries concurrently
- Downloads files asynchronously
- Minimal database load with efficient queries

## Benefits of Teacher ID Filtering

1. **Resource Efficiency**: Reduces unnecessary processing when only specific teacher entries need to be monitored
2. **Scalability**: Allows running multiple scheduler instances for different teachers
3. **Debugging**: Makes it easier to troubleshoot issues for specific teachers
4. **Performance**: Reduces database query load when filtering is applied