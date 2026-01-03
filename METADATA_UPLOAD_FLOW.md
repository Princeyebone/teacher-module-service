# Metadata-Only Upload Flow

This document describes the new file upload flow where the frontend sends only metadata to the backend, and the backend generates signed URLs for direct GCS uploads.

## Overview

Instead of sending the entire file content to the backend, the frontend now:
1. Sends metadata (file name, size, type, and other required fields) to the backend
2. Receives signed URLs from the backend
3. Uploads files directly to Google Cloud Storage (GCS)
4. The backend automatically processes files for RAG after they're uploaded to GCS

## Benefits

- Reduced bandwidth usage (no file content sent to backend)
- Faster upload experience (direct GCS upload)
- Better scalability (backend doesn't need to handle file content)
- Improved security (files go directly to GCS)

## Endpoints

### 1. Curriculum Upload (`/api/teacher/curriculum/upload`)

**Method:** POST  
**Authentication:** Required (Bearer Token)  
**Form Data:**
- `subject` (string, required)
- `class_name` (string, required)
- `education_system` (string, required)
- `education_level` (string, required)
- `country_name` (string, optional)
- `file_name` (string, required) - Original file name
- `file_size` (integer, required) - File size in bytes
- `file_type` (string, required) - MIME type (e.g., "application/pdf")

**Response:**
```json
{
  "status": "success",
  "message": "Signed URL generated successfully. Use it to upload file to GCS.",
  "signed_urls": {
    "primary": "https://storage.googleapis.com/..."
  },
  "gcs_file_names": {
    "primary": "curriculum/{teacher_id}/{class_name}/{subject}.{ext}"
  },
  "content_type": "application/pdf",
  "teacher_id": "uuid",
  "subject": "Mathematics",
  "class_name": "Grade 10A",
  "education_system": "National Curriculum",
  "education_level": "Secondary",
  "knowledge_id": "123",
  "note": "Use the signed_url to upload your file directly to Google Cloud Storage. RAG processing will begin automatically in 120 seconds."
}
```

### 2. Semester Plan Upload (`/api/teacher/sem-plan/upload`)

**Method:** POST  
**Authentication:** Required (Bearer Token)  
**Form Data:**
- `subject` (string, required)
- `class_name` (string, required)
- `education_system` (string, required)
- `education_level` (string, required)
- `country_name` (string, optional)
- `file_name` (string, required) - Original file name
- `file_size` (integer, required) - File size in bytes
- `file_type` (string, required) - MIME type (e.g., "application/pdf")

**Response:**
(Same structure as curriculum upload)

### 3. RAG Upload (`/api/teacher/rag/upload`)

**Method:** POST  
**Authentication:** Required (Bearer Token)  
**Form Data:**
- `file_name` (string, required) - Original file name
- `file_size` (integer, required) - File size in bytes
- `file_type` (string, required) - MIME type (e.g., "application/pdf")
- `subject` (string, required)
- `notes` (string, optional)
- `level` (string, required)
- `region` (string, required)
- `source_url` (string, optional)
- `file_path_field` (string, optional)
- `pillar` (string, required)

**Response:**
```json
{
  "status": "success",
  "message": "Signed URL generated successfully. Use it to upload file to GCS.",
  "signed_url": "https://storage.googleapis.com/...",
  "gcs_file_name": "teacher_rag_upload/{pillar_folder}/{filename}",
  "content_type": "application/pdf",
  "teacher_id": "uuid",
  "knowledge_id": "123",
  "metadata": {
    "subject": "Biology",
    "notes": "Chapter 3: Cell Biology",
    "level": "High School",
    "region": "Nigeria",
    "source_url": "https://example.com/biology-textbook",
    "file_path": "gs://bucket/teacher_rag_upload/curriculum/biology_textbook_chapter3.pdf",
    "pillar": "curriculum"
  },
  "note": "Use the signed_url to upload your file directly to Google Cloud Storage. RAG processing will begin automatically after upload."
}
```

## Frontend Implementation Flow

### Step 1: Collect File Metadata
```javascript
// Get file metadata from file input
const file = fileInput.files[0];
const metadata = {
  file_name: file.name,
  file_size: file.size,
  file_type: file.type
};
```

### Step 2: Send Metadata to Backend
```javascript
// Send metadata to appropriate endpoint
const response = await fetch('/api/teacher/curriculum/upload', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${authToken}`
  },
  body: new FormDataWithMetadata(metadata)
});
```

### Step 3: Receive Signed URL
```javascript
const result = await response.json();
const signedUrl = result.signed_urls.primary; // or result.signed_url for RAG
```

### Step 4: Upload Directly to GCS
```javascript
// Upload file content directly to GCS
await fetch(signedUrl, {
  method: 'PUT',
  headers: {
    'Content-Type': file.type
  },
  body: fileContent
});
```

### Step 5: Backend Processes Automatically
- For curriculum/semester plans: RAG processing begins 120 seconds after upload
- For RAG uploads: Processing begins immediately after upload

## Backend Processing

### RAG Scheduler
The backend runs a scheduler that:
1. Monitors KnowledgeMetadata entries
2. Waits 120 seconds after creation (for curriculum/semester plans)
3. Downloads files from GCS
4. Processes files through text extraction → chunking → embedding pipeline
5. Stores embeddings in the database

### Duplicate Prevention
All endpoints implement duplicate prevention:
- Checks for existing records with same teacher_id, subject, class_name, and filename
- Updates existing records instead of creating duplicates
- Maintains file_path and other metadata correctly

## Testing

See `test_metadata_upload.py` for example implementation of the new flow.

## Migration Notes

Existing frontend code that sends file content should be updated to:
1. Extract file metadata before upload
2. Send metadata to backend endpoints
3. Use returned signed URLs for GCS uploads
4. Remove any local file saving logic

The backend changes are backward compatible in terms of API structure, but the endpoints now expect metadata fields instead of file content.