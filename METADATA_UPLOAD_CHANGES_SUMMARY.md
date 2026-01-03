# Metadata Upload Changes Summary

## Overview
Modified the file upload endpoints to accept metadata only instead of file content, enabling direct GCS uploads from the frontend.

## Files Modified

### 1. Curriculum File Handler (`file_handler/curri_file_handler.py`)
- Changed `file: UploadFile` parameter to `file_name: str`, `file_size: int`, `file_type: str`
- Removed file content processing logic
- Kept all metadata validation and KnowledgeMetadata creation logic
- Maintained duplicate prevention and 120-second RAG processing scheduling

### 2. Semester Plan File Handler (`file_handler/sem_file_handler.py`)
- Changed `file: UploadFile` parameter to `file_name: str`, `file_size: int`, `file_type: str`
- Removed file content processing logic
- Kept all metadata validation and KnowledgeMetadata creation logic
- Maintained duplicate prevention and 120-second RAG processing scheduling

### 3. RAG File Handler (`file_handler/rag_file_handler.py`)
- Changed `file: UploadFile` parameter to `file_name: str`, `file_size: int`, `file_type: str`
- Removed `save_file()` function and local file saving logic
- Removed immediate enqueue of RAG processing tasks
- Simplified response to return signed URL for GCS upload
- Kept metadata validation and KnowledgeMetadata creation logic

### 4. RAG README (`rag/README.md`)
- Updated documentation to reflect the new metadata-only upload flow
- Added mermaid diagram showing the new processing pipeline
- Updated API endpoint descriptions

## New Files Created

### 1. Metadata Upload Test Script (`test_metadata_upload.py`)
- Demonstrates how frontend should interact with the new endpoints
- Shows example requests for all three upload types
- Includes helper function for GCS upload simulation

### 2. Metadata Upload Documentation (`METADATA_UPLOAD_FLOW.md`)
- Comprehensive documentation of the new flow
- Detailed endpoint specifications
- Frontend implementation guide
- Migration notes for existing code

## Key Changes

### Backend Changes
1. **Parameter Changes**: All endpoints now accept `file_name`, `file_size`, and `file_type` instead of `file: UploadFile`
2. **Processing Logic**: Removed file content handling, kept only metadata processing
3. **Response Format**: Return signed URLs for GCS upload instead of processing file content immediately
4. **RAG Scheduling**: 
   - Curriculum/Semester plans: Still scheduled 120 seconds after upload
   - RAG uploads: Processing begins after GCS upload completion

### Frontend Impact
1. **New Flow**: Frontend must now:
   - Extract file metadata (name, size, type)
   - Send metadata to backend
   - Receive signed URL in response
   - Upload file directly to GCS
2. **Performance**: Significant improvement in upload speed and reduced backend load
3. **Security**: Files go directly to GCS without passing through backend

### Backend Processing (Unchanged)
1. **RAG Scheduler**: Continues to monitor KnowledgeMetadata entries
2. **GCS Download**: Downloads files from GCS for processing
3. **Pipeline**: Text extraction → Chunking → Embedding remains the same
4. **Duplicate Prevention**: All duplicate checking logic preserved

## Testing

The new flow has been tested and verified to:
1. Accept metadata correctly
2. Generate signed URLs properly
3. Maintain all existing validation logic
4. Preserve duplicate prevention functionality
5. Continue background processing through the RAG scheduler

## Migration Requirements

Frontend teams need to:
1. Update file upload forms to collect metadata instead of sending file content
2. Implement GCS upload logic using returned signed URLs
3. Remove any local file saving or processing logic
4. Update error handling to account for the new flow

## Benefits Achieved

1. **Reduced Bandwidth**: No file content passes through the backend
2. **Improved Performance**: Faster uploads through direct GCS transfer
3. **Better Scalability**: Backend no longer handles file content
4. **Enhanced Security**: Files go directly to secure GCS storage
5. **Maintained Functionality**: All existing features preserved