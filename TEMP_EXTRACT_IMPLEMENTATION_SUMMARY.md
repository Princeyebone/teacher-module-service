# TempExtract Implementation Summary

## Overview
This document summarizes the implementation of the TempExtract table for temporary storage of extracted timetable data before user confirmation.

## Changes Made

### 1. Model Changes (`model.py`)
- Added `TempExtract` table with the following fields:
  - `id`: UUID (primary key)
  - `teacher_id`: UUID (foreign key to TeacherProfile)
  - `type`: String (e.g., "timetable", "academic_calendar")
  - `data`: JSONB (stored extracted data)
  - `created_at`: DateTime
  - `updated_at`: DateTime

### 2. Timetable CRUD Changes (`timetable_crud.py`)
- Modified `get_timetable` endpoint to first check TempExtract table for temporary data
- Modified `subjects` endpoint to first check TempExtract table for temporary data
- **Fused `create-timetable` and `update-timetable` into a single `save-timetable` endpoint** that automatically determines whether to create or update
- Modified `delete-timetable` endpoint to clean up TempExtract entries when deleting timetable
- Removed separate confirm/cancel endpoints as requested

### 3. Background Processing Changes (`t_ground/table_back.py`)
- Modified timetable processing to store extracted data in TempExtract table instead of WeeklyTimeTable
- Added logic to update existing TempExtract entries for the same teacher/type combination
- Added WebSocket message with type "COMPLETE_TIMETABLE" when processing is complete
- **Fixed UUID serialization issues** by converting UUID objects to strings before storing in JSON data field

## Key Features

### 1. Single Instance Per Type Per Teacher
- Each teacher can have at most one entry per type in the TempExtract table
- If a new extraction is made for the same type, the old data is replaced

### 2. Temporary Data Storage
- Extracted timetable data is stored temporarily in TempExtract table
- Permanent WeeklyTimeTable table is only updated when user explicitly saves data
- TempExtract entries are automatically cleaned up when user performs save/delete operations

### 3. Data Source Identification
- All read endpoints now include a `data_source` field indicating whether data came from:
  - `temp_extract`: Temporary data from TempExtract table
  - `weekly_timetable`: Permanent data from WeeklyTimeTable table
- This allows the frontend to determine what UI to show and what actions to enable

### 4. Fused Save Endpoint
- Single `save-timetable` endpoint that automatically determines whether to create or update
- If existing timetable data is found, it updates the data
- If no existing data is found, it creates new entries
- Automatically cleans up temporary data after saving

### 5. WebSocket Notifications
- WebSocket messages are sent with type "COMPLETE_TIMETABLE" when extraction is complete
- Frontend can listen for these messages to prompt user confirmation

### 6. UUID Serialization Fix
- Fixed issues with storing UUID objects in JSON data fields
- All UUID objects are converted to strings before storage
- Ensures proper JSON serialization for database operations

### 7. Future Extensibility
- The system is designed to support other types like "academic_calendar"
- Each teacher can have at most one entry per type

## API Endpoints

### Modified Endpoints
- `GET /api/get-timetable` - Returns temporary data if available (with `data_source: "temp_extract"`), otherwise permanent data (with `data_source: "weekly_timetable"`)
- `GET /api/subjects` - Returns subjects from temporary data if available (with `data_source: "temp_extract"`), otherwise permanent data (with `data_source: "weekly_timetable"`)
- `POST /api/save-timetable` - **Fused endpoint** that either creates new timetable entries or updates existing ones, and automatically cleans up any temporary data
- `DELETE /api/delete-timetable` - Deletes permanent timetable entries and automatically cleans up any temporary data

## Data Flow

1. User uploads timetable file
2. Background processing extracts data
3. Extracted data is stored in TempExtract table (with UUID objects converted to strings)
4. WebSocket message is sent to frontend with type "COMPLETE_TIMETABLE"
5. User triggers read endpoint, which returns temporary data with `data_source: "temp_extract"`
6. Frontend shows confirmation review modal based on data source
7. User edits data and clicks confirm
8. Frontend calls `save-timetable` endpoint
9. Backend either creates new entries or updates existing ones, and cleans up TempExtract

## Database Schema

```sql
CREATE TABLE tempextract (
    id UUID PRIMARY KEY,
    teacher_id UUID REFERENCES teacherprofile(id),
    type VARCHAR,
    data JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## Frontend Integration Guide

### Reading Data
When calling `GET /api/get-timetable` or `GET /api/subjects`:
- Check the `data_source` field in the response
- If `data_source` is `"temp_extract"`, show confirmation review modal
- If `data_source` is `"weekly_timetable"`, show regular timetable view

### Saving Data
When calling `POST /api/save-timetable`:
- The backend automatically determines whether to create or update
- The backend automatically cleans up any temporary data for that teacher
- The response includes:
  - `operation`: Either "create" or "update" to indicate what happened
  - `temp_data_cleaned`: true if temporary data was removed

### Deleting Data
When calling `DELETE /api/delete-timetable`:
- The backend automatically cleans up any temporary data for that teacher
- The response includes `temp_data_cleaned: true` if temporary data was removed

## Benefits of Fused Save Endpoint

1. **Simplified API**: One endpoint to handle both create and update operations
2. **Idempotent**: Multiple calls with the same data produce the same result
3. **User-friendly**: Frontend doesn't need to know the current state
4. **Race condition handling**: Prevents issues where data might be created between check and operation
5. **Automatic cleanup**: Temporary data is automatically removed after saving

## UUID Serialization Fix

The implementation now properly handles UUID serialization:
- All UUID objects are converted to strings before storing in JSON data fields
- This prevents "Object of type UUID is not JSON serializable" errors
- Ensures proper database operations and WebSocket message serialization

## Future Considerations

1. Add support for "academic_calendar" type
2. Implement automatic cleanup of old temporary data
3. Add expiration timestamps for temporary data
4. Implement user notifications for pending confirmations