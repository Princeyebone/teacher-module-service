# Timetable File Processing Background Task

## Overview

The new timetable processing system handles file uploads asynchronously using ARQ background tasks. It provides intelligent text extraction based on file type and real-time progress updates via WebSocket.

## Features

### ✨ Intelligent File Processing
- **PDF Files**: Uses `pdfplumber` for digital PDFs, falls back to OCR for scanned PDFs
- **Images (JPG/PNG)**: Uses `pytesseract` OCR for text extraction  
- **DOCX Files**: Uses `python-docx` for document text extraction
- **Excel Files**: Uses `openpyxl` for spreadsheet data extraction

### ⚡ Background Processing
- Asynchronous processing using ARQ (Async Redis Queue)
- Real-time progress updates via WebSocket
- Automatic retries on failure (3 attempts)
- 5-minute timeout per job
- **Database Integration**: Automatically saves file records to `UploadedFile` table
- **File Tracking**: Maintains file metadata and extracted text for future reference

### 📡 Real-time Updates
- WebSocket notifications for processing status
- Progress tracking from upload to completion
- Error handling with detailed feedback

## Architecture

```
Client Upload → FastAPI Route → File Save → ARQ Task Queue → Background Worker
                    ↓                                              ↓
              WebSocket Connection ←← Redis Pub/Sub ←← Processing Updates
```

## File Structure

```
table_back.py              # Main background task implementation
enque_task.py             # Task enqueueing utilities (updated)
tm_file_handler.py        # FastAPI routes (updated)
run_timetable_worker.py   # Dedicated worker runner
test_timetable_processing.py  # Testing script
timetable_processing_requirements.txt  # Additional dependencies
```

## Installation

### 1. Install Python Dependencies

```bash
# Install the additional packages for file processing
pip install pdfplumber>=0.9.0
pip install pytesseract>=3.10.1
pip install Pillow>=10.0.0
pip install pdf2image>=3.1.0
pip install python-docx>=0.8.11
pip install openpyxl>=3.1.0
```

Or install from the requirements file:
```bash
pip install -r timetable_processing_requirements.txt
```

### 2. Install System Dependencies

**For OCR functionality, install tesseract:**

- **Windows**: Download from [Tesseract GitHub](https://github.com/UB-Mannheim/tesseract/wiki)
- **Linux**: `sudo apt install tesseract-ocr`
- **macOS**: `brew install tesseract`

**For PDF to Image conversion:**
- **Windows**: Install [poppler](https://github.com/oschwartz10612/poppler-windows)
- **Linux**: `sudo apt install poppler-utils`
- **macOS**: `brew install poppler`

## Usage

### 1. Start the Background Worker

```bash
# Method 1: Using the dedicated runner
python run_timetable_worker.py

# Method 2: Using ARQ directly
python -m arq table_back.timetable_worker_config

# Method 3: Run both workers together (schedule + timetable)
python -m arq background.worker_config &
python -m arq table_back.timetable_worker_config &
```

### 2. Upload Files via API

```python
# POST /timetable/upload
# Headers: Authorization: Bearer <jwt_token>
# Body: multipart/form-data with file

import requests

files = {'file': open('timetable.pdf', 'rb')}
headers = {'Authorization': 'Bearer YOUR_JWT_TOKEN'}

response = requests.post(
    'http://localhost:8000/timetable/upload',
    files=files,
    headers=headers
)

print(response.json())
# Returns: {
#   "status": "processing",
#   "job_id": "abc123",
#   "file_path": "./uploads/teacher_idtimetable.pdf",
#   "message": "File uploaded successfully. Processing in background..."
# }
```

### 3. Monitor Progress via WebSocket

```javascript
// Connect to WebSocket for real-time updates
const ws = new WebSocket('ws://localhost:8000/ws/teacher');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Processing update:', data);
    
    if (data.status === 'completed') {
        console.log('Extracted timetable:', data.extracted_data);
    }
};
```

## API Endpoints

### Upload Timetable File

```http
POST /timetable/upload
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

Response:
{
  "status": "processing",
  "job_id": "abc123-def456",
  "file_path": "./uploads/teacher_idtimetable.pdf", 
  "teacher_id": "teacher-uuid",
  "message": "File uploaded successfully. Processing in background...",
  "note": "Connect to WebSocket for real-time updates"
}
```

### Confirm Extracted Data

```http
POST /timetable/confirm/{teacher_id}
Content-Type: application/json

{
  "timetables": [
    {
      "weekday": "Monday",
      "start_time": "09:00", 
      "end_time": "10:00",
      "subject": "Mathematics",
      "pupils": "Grade 5A"
    }
  ]
}
```

## WebSocket Updates

The system sends real-time updates via WebSocket during processing:

### Processing Started
```json
{
  "status": "started",
  "message": "Processing timetable file...",
  "teacher_id": "teacher-uuid",
  "file_path": "./uploads/teacher_idtimetable.pdf"
}
```

### Text Extraction
```json
{
  "status": "processing", 
  "message": "Extracting text from pdf file...",
  "teacher_id": "teacher-uuid"
}
```

### Parsing Data
```json
{
  "status": "processing",
  "message": "Parsing timetable data...", 
  "teacher_id": "teacher-uuid"
}
```

### Processing Complete
```json
{
  "status": "completed",
  "message": "File processed successfully! Extracted 5 timetable entries.",
  "teacher_id": "teacher-uuid",
  "uploaded_file_id": "file-record-uuid",
  "extracted_data": {
    "timetables": [...],
    "raw_text": "extracted text sample...",
    "file_type": "pdf",
    "entries_count": 5,
    "file_name": "teacher_idtimetable.pdf"
  }
}
```

### Error Handling
```json
{
  "status": "error",
  "message": "Text extraction failed: No text could be extracted",
  "teacher_id": "teacher-uuid"
}
```

## Database Integration

### UploadedFile Table

The system automatically creates records in the `UploadedFile` table for tracking uploaded files:

```python
class UploadedFile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    teacher_id: UUID = Field(foreign_key="teacherprofile.id", nullable=False)
    file_name: str                    # Original filename
    file_type: str                    # "pdf", "docx", "xlsx", "image"
    purpose: str                      # "timetable" for this system
    gcs_path: Optional[str] = None    # Left blank (for future GCS integration)
    extracted_text: str | None        # Full extracted text from file
```

### Database Workflow

1. **File Processing**: Background task extracts text from uploaded file
2. **Record Creation**: Creates `UploadedFile` record with metadata and extracted text
3. **Timetable Parsing**: Parses extracted text into structured timetable data
4. **Response**: Returns both parsed data and database record ID

This allows for:
- **File Tracking**: Track all uploaded files per teacher
- **Text Storage**: Preserve extracted text for re-processing or analysis
- **Audit Trail**: Maintain history of file uploads and processing
- **Future Integration**: `gcs_path` field ready for cloud storage integration

### Querying Uploaded Files

To retrieve uploaded files for a teacher:

```python
# Get all uploaded files for a teacher
from sqlalchemy import select
from model import UploadedFile

async def get_teacher_uploaded_files(teacher_id: str, purpose: str = "timetable"):
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(UploadedFile)
            .where(UploadedFile.teacher_id == teacher_id)
            .where(UploadedFile.purpose == purpose)
            .order_by(UploadedFile.id.desc())
        )
        return result.scalars().all()

# Get specific file by ID
async def get_uploaded_file_by_id(file_id: str):
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(UploadedFile)
            .where(UploadedFile.id == file_id)
        )
        return result.scalar_one_or_none()
```

## Supported File Types

| Extension | Processor | Features |
|-----------|-----------|----------|
| `.pdf` | pdfplumber → pytesseract | Digital text extraction with OCR fallback |
| `.jpg`, `.png` | pytesseract | OCR text extraction |
| `.docx` | python-docx | Document and table text extraction |
| `.xlsx` | openpyxl | Spreadsheet data extraction |

## Configuration

The worker can be configured in `table_back.py`:

```python
timetable_worker_config = {
    'max_tries': 3,           # Retry failed jobs 3 times
    'retry_delay': 10,        # Wait 10 seconds between retries
    'job_timeout': 300,       # 5 minutes max per job
    'concurrent_jobs': 2,     # Process 2 files simultaneously
    'keep_result': 3600,      # Keep job results for 1 hour
    'max_jobs': 50            # Max jobs before worker restart
}
```

## Testing

Run the test script to verify functionality:

```bash
python test_timetable_processing.py
```

This will:
1. Create dummy test files
2. Enqueue processing jobs
3. Check job status
4. Provide instructions for running the worker

## Troubleshooting

### Common Issues

1. **"Required library not installed" errors**
   - Install missing dependencies from `timetable_processing_requirements.txt`

2. **OCR not working**
   - Install tesseract system package
   - Verify tesseract is in PATH

3. **PDF OCR failing**
   - Install pdf2image and poppler
   - Check PDF file isn't corrupted

4. **Worker not processing jobs**
   - Ensure Redis is running
   - Check worker logs for errors
   - Verify ARQ worker is started

### Logs

Worker logs are written to:
- Console output
- `timetable_worker.log` file

## Production Deployment

For production use:

1. **Run multiple workers** for scalability
2. **Monitor worker health** using process managers (systemd, supervisor)
3. **Configure proper logging** with log rotation
4. **Set up Redis persistence** for job durability
5. **Use environment variables** for configuration

```bash
# Example systemd service
[Unit]
Description=Timetable Processing Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/app
ExecStart=/app/venv/bin/python run_timetable_worker.py
Restart=always

[Install]
WantedBy=multi-user.target
```