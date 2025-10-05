# Time Serialization Fixes

This document summarizes the fixes made to resolve JSON serialization issues with datetime.time objects in the timetable processing system.

## Issues Identified

1. **TypeError: Object of type time is not JSON serializable**
   - When storing timetable data in the TempExtract table, `datetime.time` objects ([start_time](file://c:\Users\HP\tmdl5\model.py#L117-L117) and [end_time](file://c:\Users\HP\tmdl5\model.py#L118-L118)) were not being properly serialized to JSON
   - This caused database insertion failures and rollback of transactions

2. **Incorrect AI API endpoint**
   - The external_service.py was using the wrong Google API endpoint for Gemini
   - Using the correct endpoint with proper payload structure

3. **Invalid payload structure for Gemini API**
   - The payload structure was incorrect, causing a 400 error with "Please use a valid role: user, model."

4. **Incorrect data_source field placement**
   - The data_source field was being included in each timetable entry instead of as a single field for all entries
   - This made it difficult for the frontend to determine the source of the data

## Fixes Applied

### 1. Added time import to table_back.py
```python
from datetime import datetime, time
```

### 2. Added time object serialization in table_back.py
In multiple places where timetable entries are converted to JSON-serializable format:

```python
# Convert time objects to strings for JSON serialization
if 'start_time' in entry_dict and isinstance(entry_dict['start_time'], time):
    entry_dict['start_time'] = entry_dict['start_time'].isoformat()
if 'end_time' in entry_dict and isinstance(entry_dict['end_time'], time):
    entry_dict['end_time'] = entry_dict['end_time'].isoformat()
```

This was applied to three locations:
- When preparing data for TempExtract table storage
- When sending WebSocket messages
- When returning data from the function

### 3. Fixed AI API endpoint and payload in external_service.py
- Changed from Vertex AI endpoint to Generative AI endpoint:
```python
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
```

- Updated payload structure to match the correct API format with proper role specification:
```python
payload = {
    "contents": [
        {
            "role": "user",
            "parts": [
                {
                    "text": prompt
                }
            ]
        }
    ],
    "generation_config": {
        "temperature": 0.2,
        "maxOutputTokens": 8192,
        "responseMimeType": "application/json"
    }
}
```

### 4. Fixed data_source field placement in get-timetable endpoint
Updated the get-timetable endpoint in timetable_crud.py to return data_source as a single field:

```python
# For temporary data
return {
    "items": timetable_data,
    "data_source": "temp_extract"
}

# For permanent data
return {
    "items": result,
    "data_source": "weekly_timetable"
}
```

Also removed the response_model from the endpoint decorator to allow custom response structure:
```python
@router.get("/get-timetable")  # Removed response_model to allow custom response structure
```

## Files Modified

1. `t_ground/table_back.py`:
   - Added import for `time` class
   - Added time serialization logic in three places
   - Fixed WebSocket message serialization

2. `external_service.py`:
   - Fixed AI API endpoint URL
   - Updated payload structure for Gemini API with correct role specification

3. `timetable_crud.py`:
   - Modified get-timetable endpoint to return data_source as a single field
   - Removed response_model to allow custom response structure

## Testing

After these fixes, the system should properly handle:
- Storing timetable data with time objects in the TempExtract table
- Sending timetable data via WebSocket messages
- Processing timetable files through the AI service
- Converting all datetime.time objects to ISO format strings for JSON serialization
- Including data_source information in API responses as a single field for all entries

## Verification

To verify the fixes work correctly:
1. Upload a timetable file through the system
2. Check that the TempExtract table properly stores the data
3. Verify that WebSocket messages are sent without serialization errors
4. Confirm that the AI processing completes successfully
5. Check that the get-timetable endpoint returns data with data_source field as a single field for all entries