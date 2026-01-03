# Student Support Pack System - Setup Guide

## 🎯 Overview

The Student Support Pack system generates personalized learning materials for individual students based on their interests, health considerations, and learning needs.

## 🏗️ Architecture

### Event-Driven Queue System (ARQ)
- **No polling** - jobs are processed immediately when created
- Uses **Redis** as the message queue
- Same pattern as the slide builder system

### Components

1. **API Endpoint** (`file_handler/student_support_handler.py`)
   - Creates pack record in database
   - Enqueues job to Redis
   - Returns immediately with pack_id and job_id

2. **Enqueue Module** (`student_back/enqueue_support_pack.py`)
   - Handles job queuing to Redis
   - Uses Redis DB 8
   - Queue name: `student_support_queue`

3. **ARQ Worker** (`student_back/support_pack_worker.py`)
   - Listens to Redis queue
   - Processes jobs immediately
   - Generates AI content and images
   - Updates database with results

4. **Generator** (`student_back/student_support_generator.py`)
   - Core logic for content generation
   - Uses Vertex AI (Gemini) for text
   - Generates personalized images
   - Structures content into slides

## 🚀 Quick Start

### 1. Start the Worker

```bash
python student_back/support_pack_worker.py
```

You should see:
```
======================================================================
Starting Student Support Pack Worker
======================================================================
🚀 Student Support Pack worker starting up...
   Queue: student_support_queue
   Redis: localhost:6379/db8
```

### 2. Create a Support Pack via API

**Endpoint:** `POST /api/teacher/student-support`

**Request Body:**
```json
{
  "student_name": "John Doe",
  "subject": "Mathematics",
  "class_name": "Grade 10",
  "topic": "Quadratic Equations",
  "interests": ["sports", "music", "technology"],
  "health_considerations": "ADHD - needs frequent breaks"
}
```

**Response:**
```json
{
  "message": "Student support pack created and enqueued for generation",
  "pack_id": "uuid-here",
  "job_id": "arq-job-id",
  "status": "pending",
  "student_name": "John Doe",
  "topic": "Quadratic Equations"
}
```

### 3. Worker Processes the Job

The worker will:
1. Pick up the job from Redis (no delay)
2. Generate personalized content using AI
3. Create custom images
4. Structure everything into slides
5. Save to database with status "completed"

## 📊 Database Schema

### Table: `student_support_packs`

```sql
CREATE TABLE student_support_packs (
    id UUID PRIMARY KEY,
    teacher_id UUID REFERENCES teacherprofile(id),
    student_name VARCHAR(255),
    subject VARCHAR(255),
    class_name VARCHAR(255),
    edu_sys VARCHAR(100),
    edu_lvl VARCHAR(100),
    topic VARCHAR(500),
    interests JSONB,
    health_considerations TEXT,
    content_json JSONB,
    teacher_instructions TEXT,
    status VARCHAR(50),  -- pending, processing, completed, failed
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

## 🔧 Configuration

### Redis Settings
- **Host:** localhost
- **Port:** 6379
- **Database:** 8 (separate from slides=7, outlines=6)

### Worker Settings
- **Max concurrent jobs:** 2
- **Job timeout:** 20 minutes (1200 seconds)
- **Result retention:** 1 hour

## 📝 API Endpoints

### Create Support Pack
`POST /api/teacher/student-support`

### Get Support Pack
`GET /api/teacher/student-support/{pack_id}`

### List Support Packs
`GET /api/teacher/student-support?subject=Math&class_name=Grade10`

### Update Support Pack
`PUT /api/teacher/student-support/{pack_id}`

## 🐛 Troubleshooting

### Worker Not Starting
- Check Redis is running: `redis-cli ping`
- Check Redis DB 8: `redis-cli -n 8 KEYS *`

### Jobs Not Processing
- Check worker logs in `student_back/worker.log`
- Verify job was enqueued: Check API response for `job_id`
- Check Redis queue: `redis-cli -n 8 LLEN arq:queue:student_support_queue`

### Database Errors
- Ensure table exists: `\d student_support_packs` in psql
- Check database connection in `database.py`

## 🔄 Migration from Old System

### Old System (Deprecated)
- ❌ `student_back/run_workers.py` - Polling-based workers
- ❌ `student_back/worker.py` - Old worker implementation

### New System (Current)
- ✅ `student_back/support_pack_worker.py` - ARQ worker
- ✅ `student_back/enqueue_support_pack.py` - Queue management
- ✅ Event-driven, no polling

**Do NOT run `run_workers.py` anymore!**

## 📦 Dependencies

Ensure these are installed:
```bash
pip install arq redis google-cloud-aiplatform google-cloud-storage
```

## 🎨 Generated Content Structure

Each pack includes:
- **Title Slide** - Student name, topic
- **Introduction** - Personalized to student's interests
- **Content Slides** - Main lesson material with images
- **Assessment** - MCQ and essay questions
- **Teacher Instructions** - Special handling notes

## 🔐 Security

- Teacher authentication required
- Packs are teacher-scoped (can only see own packs)
- Signed URLs for images (60-minute expiry)

## 📈 Monitoring

Check worker status:
```bash
# View active jobs
redis-cli -n 8 LLEN arq:queue:student_support_queue

# View worker logs
tail -f student_back/worker.log
```

## ✅ Success Checklist

- [ ] Redis is running
- [ ] Worker is started (`support_pack_worker.py`)
- [ ] FastAPI server is running
- [ ] Database table exists
- [ ] Vertex AI credentials configured
- [ ] GCS bucket accessible

---

**Last Updated:** 2025-12-31
**System Version:** ARQ Queue-Based (v2.0)
