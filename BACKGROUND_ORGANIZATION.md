# Background Task Organization

This document describes the organization of background tasks in the TMDL5 system.

## Directory Structure

### sch_ground/
Contains the schedule generation worker and related background processing tasks.

- `background.py` - Main background task for schedule generation
- `arq_worker.py` - ARQ worker configuration and startup
- `worker_manager.py` - Worker management utilities
- `run_schedule_worker.py` - Script to run the schedule worker
- `test_saved_schedules.py` - Tests for schedule generation

### t_ground/
Contains the timetable processing worker and related background processing tasks.

- `table_back.py` - Main background task for timetable file processing
- `run_timetable_worker.py` - Script to run the timetable worker
- `test_timetable_processing.py` - Tests for timetable processing
- `test_uploaded_files_db.py` - Tests for uploaded files database operations

### ca_ground/
Contains the academic calendar processing worker and related background processing tasks.

- `calendar_back.py` - Main background task for academic calendar file processing
- `run_calendar_worker.py` - Script to run the calendar worker
- `test_calendar_processing.py` - Tests for calendar processing
- `CAL_PROCESSING_README.md` - Documentation for calendar processing

## Task Types

### Schedule Generation
Generates intelligent class schedules based on timetable and calendar data.

### Timetable Processing
Processes uploaded timetable files and extracts structured data.

### Calendar Processing
Processes uploaded academic calendar files and extracts structured data with support for additional context information.

## Worker Configuration

Each worker has specific configuration for:
- Retry policies
- Timeout settings
- Concurrent job limits
- Result retention

## Running Workers

Workers can be started using the respective run scripts:
```bash
python sch_ground/run_schedule_worker.py
python t_ground/run_timetable_worker.py
python ca_ground/run_calendar_worker.py
```