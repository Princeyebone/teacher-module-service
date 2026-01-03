# Free Plan - AI-Powered Semester Plan Generation

## Overview

The **Free Plan** feature allows teachers to generate comprehensive semester plans using only AI and web search, **without uploading any documents**. This is perfect for teachers who don't have curriculum documents readily available.

## How It Works

### 1. Teacher Input
The teacher provides:
- **Subject/Course** (e.g., "Mathematics", "Biology")
- **Class/Pupil Level** (e.g., "Grade 4", "Level 100", "Class 2")
- **Academic Level** (university/college/k12/other)
- **Education System** (e.g., "Ghana", "Cambridge", "IB")
- **Topic Description** (optional) - Focus area for the plan
- **Learning Objective** (optional) - Specific goals to achieve

### 2. AI Web Search
The AI:
- Searches the web for official curriculum documents
- Finds strands, substrands, content standards, and indicators
- Identifies appropriate learning outcomes
- Maps everything to the teacher's timetable

### 3. Plan Generation
The system:
- Uses the teacher's timetable (weeks and sessions)
- Distributes curriculum content across available sessions
- Ensures topic focus (if provided)
- Aligns with learning objectives (if provided)
- Stores the plan in the database

## Architecture

```
Frontend Input → API Endpoint → ARQ Queue → Worker → AI + Web Search → Database
```

### Components

1. **API Endpoint** (`file_handler/free_hand.py`)
   - Receives teacher input
   - Validates and fetches session data
   - Enqueues background task
   - Returns immediately

2. **Background Queue** (`free_back/enqueue_free.py`)  
   - Redis database 5
   - Queue name: `free_plan_queue`
   - Manages task distribution

3. **Workers** (`free_back/free_worker.py`)
   - 2 concurrent workers
   - Processes plan generation
   - Sends WebSocket updates

4. **Processor** (`free_back/free_processor.py`)
   - Builds AI prompt with web search instructions
   - Calls AI service (Gemini with grounding)
   - Stores results in database
   - Logs everything to `free_back/log.txt`

## Installation & Setup

### 1. Dependencies
Already included in the project:
- arq (background tasks)
- fastapi (API endpoint)
- redis (message broker)

### 2. Start Workers
```bash
# Option 1: Python script (recommended)
python free_back/run_free_workers.py

# Option 2: Manual
python free_back/free_worker.py  # Start 2 instances in separate terminals
```

### 3. Verify Workers
Check that both workers are running:
- Worker 1 and Worker 2 should show startup logs
- Redis connection should succeed
- Queue `free_plan_queue` should be active

## API Usage

### Endpoint
```
POST /api/free-plan/generate
```

### Request Body
```json
{
  "subject": "Mathematics",
  "class_name": "Grade 4",
  "academic_level": "k12",
  "education_system": "Ghana",
  "topic_description": "Fractions and Decimals",  // optional
  "learning_objective": "Students will understand equivalent fractions and convert between fractions and decimals"  // optional
}
```

### Response
```json
{
  "status": "success",
  "message": "Plan generation started for Mathematics - Grade 4",
  "job_id": "abc123...",
  "details": {
    "subject": "Mathematics",
    "class_name": "Grade 4",
    "academic_level": "k12",
    "education_system": "Ghana",
    "topic": "Fractions and Decimals",
    "objectives": "Students will understand...",
    "weeks": 15,
    "sessions": 44
  }
}
```

## WebSocket Updates

The system sends real-time updates via WebSocket:

```javascript
{
  "type": "semplan_processing",
  "status": "started",  // started → processing → storing → completed/error
  "message": "Starting AI-powered plan generation...",
  "teacher_id": "...",
  "subject": "Mathematics",
  "class_name": "Grade 4",
  "source": "free_plan"
}
```

## AI Prompt Structure

The AI receives a comprehensive prompt including:

1. **Mandatory Web Search Instructions**
   - Must search for official curriculum documents
   - Education system, academic level, subject, class
   - Semester and term context

2. **Educational Context**
   - Education system
   - Academic level (university/college/k12/other)
   - Subject and class
   - Semester and term

3. **Optional Guidance**
   - Topic description (if provided)
   - Learning objectives (if provided)

4. **Session Data**
   - Available weeks
   - Session details (dates, times)
   - Mapping constraints

5. **Output Requirements**
   - JSON format
   - Strands, substrands, content standards, indicators
   - Mapped to specific sessions

## Logging

All processing is logged to `free_back/log.txt` with sections:

1. **FREE PLAN GENERATION STARTED**
   - Teacher info, subject, class
   - Academic level, education system
   - Topic and objectives

2. **INPUT: SESSION DATA**
   - Complete session structure
   - Weeks and sessions

3. **FETCHING SEMESTER METADATA**
   - Semester name and term from db

4. **BUILDING AI PROMPT**
   - Prompt length and full content

5. **WEB SEARCH CONFIGURATION**
   - Search context
   - All metadata

6. **AI RESPONSE**
   - Response structure
   - Counts (strands, substrands, etc.)
   - Full JSON response

7. **DATABASE STORAGE**
   - Storage process
   - Success/failure

8. **COMPLETION/ERROR**
   - Final status
   - Timestamp

## Database Schema

Uses the same tables as curriculum and semplan:
- `Strand`
- `Substrand`
- `ContentStandard`
- `Indicator`

Each record includes:
- `teacher_id`
- `subject`
- `class_name`
- `weeks` array
- `sessions` array

## Comparison with Other Features

| Feature | Document Required | Web Search | Use Case |
|---------|------------------|------------|----------|
| **Semplan** | Yes (semester plan PDF) | Supplemental | Upload existing plan |
| **Curriculum** | Yes (curriculum/syllabus PDF) | Supplemental | Use official curriculum |
| **Free Plan** | No | Primary | No documents available |

## Best Practices

### 1. Provide Topic Description
```json
{
  "topic_description": "Algebra - Linear Equations and Inequalities"
}
```
Helps AI focus the search and plan content.

### 2. Add Learning Objectives
```json
{
  "learning_objective": "Students will solve multi-step linear equations and graph solutions to inequalities"
}
```
Ensures the plan aligns with your teaching goals.

### 3. Use Specific Class Names
- ✅ "Grade 4", "Level 200", "Form 3"
- ❌ "My class", "Advanced group"

Helps AI find appropriate curriculum level.

### 4. Specify Education System
- ✅ "Ghana GES", "Cambridge IGCSE", "IB MYP"
- ❌ "Standard", "Normal"

Enables accurate curriculum search.

## Troubleshooting

### Workers Not Starting
```bash
# Check Redis
redis-cli ping

# Check port 6379
netstat -an | findstr 6379

# View worker logs
python free_back/free_worker.py
```

### No Web Search Results
- Check internet connection
- Verify education system spelling
- Try more specific topic description
- Check `free_back/log.txt` for errors

### Plan Not Generated
1. Check worker status
2. View logs: `free_back/log.txt`
3. Check WebSocket connection
4. Verify session data exists

### Database Errors
- Ensure timetable is created first
- Verify academic calendar exists
- Check database connection

## Monitoring

### View Processing Logs
```bash
# Windows
Get-Content free_back\log.txt -Tail 50 -Wait

# Or open in editor
notepad free_back\log.txt
```

### Check Queue Status
```python
import asyncio
from arq import create_pool
from arq.connections import RedisSettings

async def check_queue():
    redis = await create_pool(RedisSettings(host='localhost', port=6379, database=5))
    info = await redis.info()
    print(info)
    await redis.aclose()

asyncio.run(check_queue())
```

## Performance

- **Average Processing Time**: 30-60 seconds
- **Concurrent Jobs**: 2 workers = 2 simultaneous plans
- **Timeout**: 10 minutes per job
- **Retries**: Up to 5 attempts

## Future Enhancements

1. **Curriculum Library**
   - Cache common curricula
   - Faster retrieval

2. **Multi-Language Support**
   - Search in different languages
   - Support international systems

3. **Customization**
   - Adjust difficulty level
   - Add prerequisite topics

4. **Collaboration**
   - Share generated plans
   - Department-wide templates

## Support

Check these resources:
- Logs: `free_back/log.txt`
- Worker status: Terminal running `run_free_workers.py`
- API docs: `/docs` endpoint
- WebSocket events: Browser DevTools

---

**Created**: 2025-12-09  
**Version**: 1.0  
**Workers**: 2  
**Queue**: free_plan_queue  
**Redis DB**: 5
