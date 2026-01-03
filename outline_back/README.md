# Course/Subject Outline Generation System

Automatically generates comprehensive course/subject outlines from curriculum data for the Teacher Lesson Pack feature.

---

## 📋 Overview

When a semester plan is generated (via SemPlan, Curriculum, or Free Hand), the system automatically enqueues an outline generation task that:

1. **Fetches** all curriculum data (strands, substrands, content standards, indicators)
2. **Sends** to AI for comprehensive outline generation
3. **Stores** the result in the `Outline` database table

---

## 🗄️ Database Schema

### `Outline` Table

```sql
CREATE TABLE outline (
    id INTEGER PRIMARY KEY,
    teacher_id UUID REFERENCES teacherprofile(id),
    subject VARCHAR NOT NULL,
    class_name VARCHAR NOT NULL,
    
    -- Outline content
    outline_content TEXT,  -- AI-generated outline
    
    -- Metadata
    education_system VARCHAR,
    academic_level VARCHAR,
    semester_name VARCHAR,
    term VARCHAR,
    
    -- Tracking
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

**Indexes**: 
- `teacher_id`, `subject`, `class_name`

---

## 🚀 Usage

### 1. Enqueue Outline Generation

After creating a curriculum plan, enqueue an outline task:

```python
from outline_back import enqueue_outline_generation

job = await enqueue_outline_generation(
    teacher_id="uuid-string",
    subject="Mathematics",
    class_name="Class 6",
    education_system="ges",
    academic_level="k12",
    semester_name="First Term 2024/2025",
    term="First Term",
    delay=5  # Wait 5 seconds before processing
)

print(f"Outline job queued: {job.job_id}")
```

### 2. Check Job Status

```python
from outline_back import get_outline_job_status

status = await get_outline_job_status(job.job_id)
print(status)
# {
#     "job_id": "...",
#     "status": "complete",
#     "result": {"status": "success", ...}
# }
```

### 3. Retrieve Outline

```python
from model import Outline
from sqlmodel import select

result = await session.execute(
    select(Outline).where(
        Outline.teacher_id == teacher_id,
        Outline.subject == subject,
        Outline.class_name == class_name
    )
)
outline = result.scalar_one_or_none()

if outline:
    print(outline.outline_content)  # Markdown formatted outline
```

---

## 🔧 System Components

### 1. `outline_processor.py`
- **Purpose**: Core processing logic
- **Functions**:
  - `process_outline_task()` - Main task handler
  - `fetch_curriculum_data()` - Get data from DB
  - `build_outline_prompt()` - Create AI prompt
  - `call_ai_for_outline()` - Call Gemini AI
  - `store_outline_in_db()` - Save to database

### 2. `outline_worker.py`
- **Purpose**: ARQ worker configuration
- **Queue**: `outline_queue`
- **Redis**: `localhost:6379/6`
- **Timeout**: 10 minutes per job
- **Max Jobs**: 5 concurrent

### 3. `enqueue_outline.py`
- **Purpose**: Task enqueueing
- **Functions**:
  - `enqueue_outline_generation()` - Add task to queue
  - `get_outline_job_status()` - Check job status

### 4. `run_outline_workers.py`
- **Purpose**: Run multiple workers
- **Workers**: 2 parallel workers
- **Usage**: `python outline_back/run_outline_workers.py`

---

## 📊 Data Flow

```
Plan Generated (semplan/curriculum/free) 
    ↓
Enqueue Outline Task
    ↓
Worker picks up task
    ↓
Fetch curriculum data (strands, substrands, standards, indicators)
    ↓
Build AI prompt
    ↓
Call Gemini AI
    ↓
Receive outline (markdown)
    ↓
Store in Outline table
    ↓
Complete ✅
```

---

## 🤖 AI Prompt Structure

The AI receives:

1. **Course Information**
   - Subject, Class, Education System, Academic Level, Semester, Term

2. **Curriculum Structure**
   - All strands with substrands
   - Content standards for each substrand
   - Indicators for each standard

3. **Task Requirements**
   - Course overview
   - Curriculum structure summary
   - Detailed outline for each strand/substrand
   - Learning progression
   - Teaching recommendations

**Output Format**: Professional markdown-formatted course outline

---

## 🔄 Integration with Plan Generation

### SemPlan Integration
```python
# In semplan_ground/semplan_back.py
from outline_back import enqueue_outline_generation

# After storing plan
await enqueue_outline_generation(
    teacher_id=teacher_id,
    subject=subject,
    class_name=class_name,
    ...
)
```

### Curriculum Integration
```python
# In curri_back/curri_processor.py
from outline_back import enqueue_outline_generation

# After storing plan
await enqueue_outline_generation(...)
```

### Free Plan Integration
```python
# In free_back/free_processor.py  
from outline_back import enqueue_outline_generation

# After storing plan
await enqueue_outline_generation(...)
```

---

## 🛠️ Running Workers

### Start Workers
```bash
python outline_back/run_outline_workers.py
```

Output:
```
======================================================================
Starting 2 Outline Generation Workers
======================================================================
Worker script: outline_back\outline_worker.py
Queue: outline_queue
Redis: localhost:6379/6
======================================================================

Starting worker 1/2...
✅ Worker 1 started (PID: 12345)
Starting worker 2/2...
✅ Worker 2 started (PID: 12346)

======================================================================
All 2 workers running
Press Ctrl+C to stop all workers
======================================================================
```

### Stop Workers
Press `Ctrl+C` - workers will gracefully shutdown

---

## 📝 Logging

### Log Files
- `outline_back/log.txt` - Detailed processing logs
- `outline_back/worker.log` - Worker activity logs

### Log Sections
```
====================================================================================================
  OUTLINE GENERATION STARTED - 2025-12-10T02:00:00
====================================================================================================
Task ID: abc123
Teacher ID: uuid
Subject: Mathematics
Class: Class 6
...

====================================================================================================
  FETCHING CURRICULUM DATA
====================================================================================================
Found curriculum data:
  Strands: 4
  Substrands: 8
  Content Standards: 15
  Indicators: 45
...

====================================================================================================
  OUTLINE GENERATION COMPLETED
====================================================================================================
Status: SUCCESS
```

---

## ✅ Testing

### 1. Database Migration
```bash
# Create Outline table
alembic revision --autogenerate -m "Add Outline table"
alembic upgrade head
```

### 2. Test Enqueue
```python
# test_outline.py
import asyncio
from outline_back import enqueue_outline_generation

async def test():
    job = await enqueue_outline_generation(
        teacher_id="your-uuid",
        subject="Mathematics",
        class_name="Class 6"
    )
    print(f"Job ID: {job.job_id}")

async io.run(test())
```

### 3. Start Workers
```bash
python outline_back/run_outline_workers.py
```

### 4. Check Database
```sql
SELECT * FROM outline WHERE subject = 'Mathematics';
```

---

## 🔍 Troubleshooting

### No outline generated
1. Check workers are running
2. Check Redis is running: `redis-cli ping`
3. Check logs: `outline_back/log.txt`
4. Verify curriculum data exists in DB

### Worker crashes
1. Check `outline_back/worker.log`
2. Verify imports work: `python -c "from outline_back import process_outline_task"`
3. Check Redis connection
4. Verify Gemini API key in config

### Empty outline_content
1. Check AI response in logs
2. Verify prompt is well-formed
3. Check Gemini API limits

---

## 📚 Dependencies

- **ARQ**: Task queue
- **Redis**: Message broker (DB 6)
- **Gemini AI**: Outline generation
- **SQLModel**: Database ORM
- **PostgreSQL**: Data storage

---

## 🎯 Future Enhancements

- [ ] Add outline versioning
- [ ] Support outline regeneration
- [ ] Add custom outline templates
- [ ] Export outline to PDF
- [ ] Integration with Lesson Brief
- [ ] Integration with Lesson Slides

---

**System Status**: ✅ **FULLY IMPLEMENTED AND READY TO USE**
