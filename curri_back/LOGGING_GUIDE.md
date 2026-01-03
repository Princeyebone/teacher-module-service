# Curriculum Background Processing - Comprehensive Logging Guide

## Log File Location
All detailed curriculum processing logs are written to:
```
curri_back/log.txt
```

## Log Format
```
YYYY-MM-DD HH:MM:SS,mmm - LEVEL - Message
```

## What Gets Logged

### 1. **PROCESSING STARTED**
- Teacher ID
- Subject
- Class Name
- GCS File Path
- File Name
- Knowledge ID
- Timestamp

### 2. **INPUT: SESSION DATA**
Comprehensive logging of session data structure:
- Full session data JSON (pretty-printed)
- Semester start date
- Semester end date
- Number of weeks
- Session count per week

**Example:**
```json
{
  "semester_start_date": "2025-01-06",
  "semester_end_date": "2025-04-15",
  "weekly_sessions": {
    "Week 1": {
      "week_number": 1,
      "sessions": [...]
    }
  }
}
```

### 3. **STEP: RETRIEVAL - Searching for Syllabus Content**

#### Retrieval Query Parameters:
- Query string
- Subject filter
- Pillar filter (syllabus/curriculum)
- Class level filter
- Limit (default: 4)
- Min similarity threshold
- Hybrid search enabled/disabled
- Keyword weight

#### Retrieval Results:
For each retrieved chunk:
- Similarity score
- Combined score
- Keyword score
- Knowledge ID
- Subject
- Pillar
- Chunk order
- First 500 characters of chunk text
- Full chunk JSON

**Also logs:**
- Total chunks retrieved
- Fallback attempts (if syllabus yields no results)
- Complete JSON of all retrieval results

### 4. **STEP: AI PROCESSING - Building Prompt and Sending to AI**

#### AI Prompt:
- Prompt length (character count)
- **Complete prompt content** (full text sent to AI)

#### AI Response:
- Response success/failure status
- Response length (character count)
- Response structure summary:
  - Number of strands
  - Number of substrands
  - Number of content standards
  - Number of indicators
- **Complete AI response JSON** (fully formatted)

**On Error:**
-AI error message
- Full error response JSON

### 5. **STEP: DATABASE STORAGE**
- Storage initiation log
- Storage completion status
- Any errors during storage

### 6. **COMPLETION**
- Final timestamp
- Teacher ID
- Subject
- Class name
- Status: SUCCESS

### 7. **ERROR HANDLING**
When processing fails:
- Error message
- Error type (exception class)
- Teacher ID
- Subject
- Class name
- GCS file path
- Error timestamp
- **Full Python traceback**

## Log Sections

Each major phase is clearly separated with headers:
```
====================================================================================================
  SECTION TITLE
====================================================================================================
```

## Usage Examples

### Viewing Recent Processing
```bash
# View last 100 lines
Get-Content curri_back\log.txt -Tail 100

# View all processing for a specific teacher
Select-String -Path curri_back\log.txt -Pattern "teacher-uuid-here"

# View only errors
Select-String -Path curri_back\log.txt -Pattern "ERROR"
```

### Finding Specific Information
```bash
# Find all retrieval results
Select-String -Path curri_back\log.txt -Pattern "RETRIEVAL RESULTS" -Context 50

# Find all AI responses
Select-String -Path curri_back\log.txt -Pattern "AI RESPONSE" -Context 100

# Find failed processings
Select-String -Path curri_back\log.txt -Pattern "FAILED - ERROR"
```

## What You Can Debug With These Logs

✅ **Session Data Issues**: Verify the exact session structure sent to AI  
✅ **Retrieval Problems**: See what chunks were retrieved and their relevance scores  
✅ **AI Prompt Issues**: Review the exact prompt sent to AI  
✅ **AI Response Format**: Check if AI is returning the expected JSON structure  
✅ **Database Storage Errors**: Identify issues when storing parsed data  
✅ **Processing Flow**: Track the complete flow from start to finish  
✅ **Error Root Causes**: Full tracebacks for debugging exceptions  

## Log Rotation

⚠️ The log file uses append mode (`mode='a'`). Consider implementing log rotation if the file grows too large.

**Recommended:** Use Windows Task Scheduler or a cron job to archive logs periodically:
```powershell
# Example: Archive logs older than 7 days
$date = (Get-Date).AddDays(-7).ToString("yyyyMMdd")
Move-Item curri_back\log.txt "curri_back\log_$date.txt" -ErrorAction SilentlyContinue
```

## Tips

1. **Use JSON pretty-printing** when viewing JSON sections in the log
2. **Search by teacher ID** to track individual user processing
3. **Cross-reference timestamps** with WebSocket messages sent to frontend
4. **Compare retrieval results** across different queries to tune parameters
5. **Analyze AI prompts** to improve curriculum plan quality
