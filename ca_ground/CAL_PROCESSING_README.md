# Academic Calendar Processing

This directory contains the background processing functionality for academic calendar file uploads.

## Components

### `calendar_back.py`
- Contains the main background task for processing academic calendar files
- Implements text extraction from various file types (PDF, DOCX, XLSX, images, TXT)
- Provides AI-powered parsing of calendar data with support for additional context
- Saves extracted data to temporary storage (TempExtract table) for user review with type "academic calendar"
- Ensures only one entry per teacher_id for type "academic calendar"
- Automatically deletes temporary files after processing
- Sends WebSocket messages with type "COMPLETED_ACADEMIC_CALENDER" upon completion

### `run_calendar_worker.py`
- Runner script for the ARQ worker that processes calendar file tasks

## Supported File Types
- PDF
- Images (JPG, PNG, BMP, TIFF)
- DOCX
- XLSX/XLS
- TXT

## Processing Flow
1. Teacher uploads academic calendar file through the API
2. File is saved locally with naming convention: `academic_calendar/{teacher_id}.{extension}`
3. Background task is enqueued for processing with additional context data
4. Text is extracted from the file using appropriate methods
5. AI processing is attempted to parse structured calendar data using the additional context
6. Extracted data is saved to TempExtract table (NOT AcademicCalendar table) for user review
7. WebSocket notifications are sent throughout the process:
   - "started" - Processing begins
   - "processing" - Text extraction and AI processing
   - "complete" with type "COMPLETED_ACADEMIC_CALENDER" - Processing completed
   - "error" - If any errors occur
8. Temporary file is automatically deleted after processing
9. Teacher reviews the extracted data through the frontend
10. Confirmed data is saved to the main AcademicCalendar and CalendarEvent tables through the save endpoint

## Additional Data Support
The calendar processing now supports additional context data that can be passed from the frontend:
- Academic year information
- Institution type
- Semester type
- Current semester details
- Multiple cohort information
- Cohort levels

This additional data is compiled from the form fields and used by the AI prompt builder to generate more accurate calendar data. Both the GCS storage location and extracted text are injected into the AI prompt for better context.