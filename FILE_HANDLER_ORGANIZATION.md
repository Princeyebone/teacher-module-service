# File Handler Organization

This document describes the organization of file handler modules into the dedicated `file_handler/` package for better maintainability and modular structure.

## 📁 Folder Structure

### `file_handler/` - File Upload & Processing Handlers
Contains all file upload and processing handlers for different types of files in the TMDL5 system.

**Files:**
- `ca_file_handler.py` - Calendar file upload and processing
- `sem_file_handler.py` - Semester mapping file upload and processing  
- `tm_file_handler.py` - Timetable file upload and processing
- `__init__.py` - Package initialization

## 🔧 Handler Descriptions

### 📅 Calendar File Handler (`ca_file_handler.py`)
**Purpose:** Handles calendar-related file uploads and data extraction.

**Features:**
- Calendar file upload endpoint `/calendar/upload`
- Extracts academic calendar data (semester dates, events, holidays)
- Processes calendar events with scheduling information
- Mock data extraction for development/testing

**API Endpoints:**
```python
POST /calendar/upload
```

### 📚 Semester File Handler (`sem_file_handler.py`) 
**Purpose:** Manages semester mapping and curriculum planning file operations.

**Features:**
- Available weeks/sessions endpoint for curriculum planning
- Integration with Academic Calendar and Class Sessions
- Strand table management for booked weeks
- Session availability calculation
- File upload with timestamp and UUID naming

**API Endpoints:**
```python
GET /available-weeks-sessions/{subject}/{class_name}
```

### ⏰ Timetable File Handler (`tm_file_handler.py`)
**Purpose:** Handles timetable file uploads with background processing.

**Features:**
- Timetable file upload endpoint `/timetable/upload`
- Background processing via ARQ tasks
- Multi-format file support (PDF, images, DOCX, XLSX)
- Real-time WebSocket updates during processing
- Teacher-specific file naming convention

**API Endpoints:**
```python
POST /timetable/upload
POST /timetable/confirm/{teacher_id}
```

## 🔗 Integration Points

### Background Processing
- [`tm_file_handler.py`](c:\Users\HP\tmdl5\file_handler\tm_file_handler.py) integrates with [`enque_task.py`](c:\Users\HP\tmdl5\enque_task.py) for background processing
- Uses [`t_ground/table_back.py`](c:\Users\HP\tmdl5\t_ground\table_back.py) for actual file processing tasks

### Main Application
- All handlers are imported in [`main.py`](c:\Users\HP\tmdl5\main.py) and registered as FastAPI routers
- Each handler provides a router with appropriate tags and prefixes

### Authentication
- All handlers use [`dependencies.py`](c:\Users\HP\tmdl5\dependencies.py) for authentication via `get_current_teacher`
- Teacher ID extraction from JWT tokens

### Database Integration
- All handlers use [`database.py`](c:\Users\HP\tmdl5\database.py) for database sessions
- Integration with various models from [`model.py`](c:\Users\HP\tmdl5\model.py)

## 📂 File Storage

### Upload Directory
```python
UPLOAD_DIR = "./uploads"
```

### Naming Conventions
- **Timetable files:** `{teacher_id}timetable.{extension}`
- **General files:** `{unique_id}_{timestamp}.{extension}`
- **Teacher-specific:** `{teacher_id}_{file_id}.{extension}`

## 🚀 Usage Examples

### Import from Package
```python
# In main.py
import file_handler.tm_file_handler as tm_file_handler
import file_handler.ca_file_handler as ca_file_handler
import file_handler.sem_file_handler as sem_file_handler

# Register routers
app.include_router(tm_file_handler.router, prefix="/api/teacher")
app.include_router(ca_file_handler.router, prefix="/api/teacher")
app.include_router(sem_file_handler.router, prefix="/api/teacher")
```

### Direct Module Access
```python
from file_handler import tm_file_handler, ca_file_handler, sem_file_handler
```

## 🔄 Processing Workflow

### Timetable Processing Flow
1. **Upload:** File uploaded via `/timetable/upload`
2. **Storage:** File saved with teacher-specific naming
3. **Validation:** File type and size validation
4. **Queue:** Background processing task enqueued
5. **Processing:** Text extraction and AI parsing (in background)
6. **Notification:** Real-time WebSocket updates
7. **Confirmation:** Optional confirmation endpoint for manual verification

### Calendar Processing Flow
1. **Upload:** File uploaded via `/calendar/upload`
2. **Storage:** File saved to uploads directory
3. **Extraction:** Immediate data extraction (mock for now)
4. **Response:** Extracted calendar data returned

### Semester Mapping Flow
1. **Query:** Available weeks requested for subject/class
2. **Calculation:** Week numbers calculated from academic calendar
3. **Filtering:** Booked weeks filtered out via Strand table
4. **Response:** Available weeks and sessions returned

## 🛠️ Configuration

### Supported File Types
- **PDF:** `.pdf` files
- **Images:** `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`
- **Documents:** `.docx`, `.xls`, `.xlsx`

### File Size Limits
- Default limit handling via FastAPI
- Custom validation in individual handlers

### Error Handling
- Comprehensive exception handling with appropriate HTTP status codes
- Logging via [`logger.py`](c:\Users\HP\tmdl5\logger.py)
- Detailed error messages for debugging

## 📋 Benefits of Organization

1. **Modular Structure:** Each file type has its dedicated handler
2. **Clear Separation:** Upload, processing, and storage logic separated
3. **Easier Maintenance:** Related functionality grouped together
4. **Consistent Interfaces:** All handlers follow similar patterns
5. **Scalable Architecture:** Easy to add new file type handlers
6. **Better Testing:** Individual handlers can be tested separately

## 🔄 Migration Notes

- All existing API endpoints remain unchanged
- Import paths updated in [`main.py`](c:\Users\HP\tmdl5\main.py)
- No database schema changes required
- File storage locations remain the same
- Background processing integration maintained