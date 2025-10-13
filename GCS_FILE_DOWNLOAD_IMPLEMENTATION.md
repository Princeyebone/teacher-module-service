# GCS File Download Implementation

## Overview
This document explains how files are downloaded from Google Cloud Storage (GCS) in the semester plan processing system.

## Implementation Flow

### 1. File Search and Download Endpoint
The process starts with the `/semester-mapper/ai-plan` endpoint in `file_handler/sem_file_handler.py`:

1. **File Search**: The system searches for files in two possible GCS locations:
   - `sem_plan/{teacher_id}/{class_name}/{subject}.{extension}`
   - `curriculum/{teacher_id}/{class_name}/{subject}.{extension}`

2. **File Detection**: It checks for common file extensions (pdf, docx, txt, jpg, png)

3. **File Download**: Uses the `get_file_from_gcs` utility function to download the file content

### 2. GCS Utility Functions
The core functionality is implemented in `gcs_utils.py`:

#### get_file_from_gcs Function
```python
def get_file_from_gcs(bucket_name: str, blob_name: str) -> Optional[bytes]:
    """
    Download file content from GCS
    
    Args:
        bucket_name: Name of the GCS bucket
        blob_name: Name of the blob (file) in GCS
    
    Returns:
        File content as bytes, or None if not found
    """
```

**Key Features**:
- Uses the GCS client initialized with service account credentials
- Downloads file content as bytes
- Handles file not found scenarios gracefully
- Provides detailed logging for debugging

#### generate_signed_url Function
```python
def generate_signed_url(bucket_name: str, blob_name: str, content_type: str = "application/octet-stream", expiration: int = 86400) -> str:
    """
    Generate a signed URL for uploading a file to GCS
    """
```

**Key Features**:
- Generates signed URLs for both upload and download operations
- Supports custom content types
- Configurable expiration time
- Uses V4 signing for security

### 3. File Processing Workflow

#### Step 1: File Discovery
```python
# In sem_file_handler.py
file_content = get_file_from_gcs(settings.GCS_BUCKET_NAME, file_path)
```

#### Step 2: Local Storage
The downloaded file content is saved locally:
```python
# Save the downloaded file locally
local_file_path = os.path.join(semplan_ground_dir, f"{teacher_id}_{uuid.uuid4().hex}_{os.path.basename(selected_file_path)}")
with open(local_file_path, "wb") as f:
    f.write(selected_file_content)
```

#### Step 3: Background Processing
The file is processed by the background task in `semplan_back.py`:
```python
# Extract text based on file type
if file_type == 'text':
    extracted_text = FileExtractor.extract_from_text(file_path)
elif file_type == 'pdf':
    extracted_text = FileExtractor.extract_from_pdf(file_path)
# ... other file types
```

#### Step 4: File Cleanup
After processing, the temporary local file is deleted:
```python
# DELETE THE FILE AFTER EXTRACTION - as per requirements
if os.path.exists(file_path):
    os.remove(file_path)
```

### 4. Signed URL Generation for Frontend Access

When storing AI responses in the TempExtract table, a signed URL is generated for frontend access:

```python
# In semplan_back.py - store_ai_response_in_temp_extract function
if gcs_file_name:
    try:
        from gcs_utils import generate_signed_url
        from config import settings
        # Generate a signed URL that expires in 7 days (604800 seconds)
        signed_url = generate_signed_url(
            settings.GCS_BUCKET_NAME, 
            gcs_file_name, 
            expiration=604800
        )
    except Exception as e:
        logger.error(f"[SEMPLAN] Failed to generate signed URL: {e}")
        signed_url = None
```

## Key Components

### 1. GCS Client Initialization
```python
def get_gcs_client():
    """Initialize and return GCS client"""
    try:
        if settings.GCS_SERVICE_ACCOUNT_JSON:
            # Handle both JSON content and file path
            if settings.GCS_SERVICE_ACCOUNT_JSON.startswith('{'):
                # JSON content
                credentials_info = json.loads(settings.GCS_SERVICE_ACCOUNT_JSON)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
                client = storage.Client(credentials=credentials, project=settings.GCS_PROJECT_ID)
            else:
                # File path
                client = storage.Client.from_service_account_json(
                    settings.GCS_SERVICE_ACCOUNT_JSON, 
                    project=settings.GCS_PROJECT_ID
                )
        else:
            # Use default credentials (for development)
            client = storage.Client(project=settings.GCS_PROJECT_ID)
        return client
    except Exception as e:
        logger.error(f"❌ Failed to initialize GCS client: {e}")
        raise
```

### 2. File Type Detection
```python
# File type mappings
SUPPORTED_EXTENSIONS = {
    'pdf': 'pdf',
    'jpg': 'image', 'jpeg': 'image', 'png': 'image', 'bmp': 'image', 'tiff': 'image',
    'docx': 'docx',
    'xlsx': 'excel', 'xls': 'excel',
    'txt': 'text'
}
```

### 3. Text Extraction
Different extraction methods based on file type:
- **PDF**: Uses pdfplumber with pytesseract OCR fallback
- **Images**: Uses pytesseract OCR
- **DOCX**: Uses python-docx
- **Excel**: Uses openpyxl
- **Text**: Direct file reading

## Security Considerations

1. **Authentication**: Uses service account credentials for GCS access
2. **Signed URLs**: Time-limited access to files
3. **Content Type Validation**: Ensures proper MIME types
4. **File Cleanup**: Temporary files are deleted after processing

## Error Handling

1. **File Not Found**: Graceful handling with appropriate HTTP responses
2. **Download Failures**: Detailed logging and error propagation
3. **Processing Errors**: Comprehensive exception handling with tracebacks
4. **Cleanup Failures**: Non-blocking error handling for file deletion

## Logging and Monitoring

The implementation includes comprehensive logging:
- File discovery and download status
- Processing progress and results
- Error conditions and failures
- Performance metrics (file sizes, processing times)

## Configuration

The system uses settings from `config.py`:
- `GCS_SERVICE_ACCOUNT_JSON`: Service account credentials
- `GCS_PROJECT_ID`: Google Cloud project ID
- `GCS_BUCKET_NAME`: Name of the GCS bucket

## Data Flow Summary

1. **Frontend** uploads files to GCS using signed URLs
2. **AI Planning Endpoint** searches for files in GCS
3. **GCS Utility** downloads file content as bytes
4. **Local Storage** saves file temporarily
5. **Background Task** processes file content
6. **Text Extraction** converts files to text
7. **AI Processing** analyzes extracted text
8. **TempExtract Storage** saves results with signed URL
9. **Frontend Access** retrieves results with signed URL access to original file