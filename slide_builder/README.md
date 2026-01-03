# Slide Builder Module

AI-powered lesson slide generation system.

## Overview

This module automatically generates structured JSON lesson slides for teachers. It runs on a schedule and creates slides at **12 AM (midnight)** in each teacher's local timezone.

## Files Overview

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `slide_scheduler.py` | APScheduler setup, hourly trigger |
| `slide_processor.py` | Main logic: timezone check, data fetching, AI call, persistence |
| `slide_prompts.py` | Prompt template builder for Vertex AI |
| `slide_schema.py` | Pydantic models for JSON validation |
| `run_slide_scheduler.py` | Entry point to start the scheduler |
| `create_slides_tables.sql` | Database migration script |

## Database Setup

Run the SQL migration first:

```bash
psql -U postgres -h localhost -d tmdl5 -p 5433 -f slide_builder/create_slides_tables.sql
```

## Usage

### Start the Scheduler

```bash
python slide_builder/run_slide_scheduler.py
```

Or as a module:

```bash
python -m slide_builder.run_slide_scheduler
```

### Manual Test Run

```python
import asyncio
from slide_builder.slide_processor import run_slide_generation_cycle

asyncio.run(run_slide_generation_cycle())
```

## How It Works

### Scheduler Flow

1. **Every hour** (at :00), the scheduler triggers the main operation
2. **Fetches all teachers** from the database who have a country set
3. **For each teacher**:
   - Gets their timezone from their country
   - Checks if their local time is **exactly 12 AM (midnight)**
   - If NOT midnight → Skip
   - If AT midnight → Proceed to generate slides

### Slide Generation Flow

For each teacher at midnight:

1. **Get tomorrow's sessions** from ClassSession table
2. **For each session**:
   - Find curriculum data (strand, substrand, content standard, indicator)
   - Build AI prompt with curriculum context
   - Call Vertex AI to generate slides JSON
   - **Validate JSON against schema**
   - Persist to `slides` table
   - Extract image prompts and queue to `slide_images` table

## Slide Schema (Strict)

The AI output MUST conform to this schema:

```json
{
  "lesson_id": "uuid",
  "subject": "string",
  "class_level": "string",
  "topic": "string",
  "slides": [
    {
      "id": "uuid",
      "type": "title | content | image_content | assessment",
      "layout": "title_center | text_only | image_left_text_right | image_top_text_bottom | assessment",
      "content": {
        "title": "string (optional)",
        "heading": "string (optional)",
        "bullet_points": ["string (max 5)"],
        "questions": ["string"],
        "image": {
          "prompt": "string",
          "style": "flat educational diagram | photo | illustration",
          "alt": "string"
        }
      }
    }
  ]
}
```

### Strict Rules

- ❌ No custom layouts allowed
- ❌ No markdown in content
- ❌ No extra keys
- ⚠️ Bullet points max 5 per slide
- ⚠️ Images are prompts only (generated separately)

## Database Schema

```sql
CREATE TABLE slides (
    id UUID PRIMARY KEY,
    teacher_id UUID NOT NULL,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    topic VARCHAR(500),
    indicator_ids JSONB DEFAULT '[]',
    content_json JSONB NOT NULL,
    generation_status VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    UNIQUE(teacher_id, subject, class_name, topic)
);

CREATE TABLE slide_images (
    id UUID PRIMARY KEY,
    slide_id UUID NOT NULL REFERENCES slides(id),
    slide_item_id VARCHAR(255) NOT NULL,
    prompt TEXT NOT NULL,
    style VARCHAR(100),
    alt_text TEXT,
    image_url TEXT,
    gcs_path TEXT,
    status VARCHAR(50) DEFAULT 'pending'
);
```

## Logs

Logs are written to `slide_builder/slide_log.txt`.

## Image Generation Worker

Images are **not generated inline**. The slide processor:
1. Extracts image prompts from AI-generated slides
2. Saves them to `slide_images` table with `status = 'pending'`
3. A separate image worker (TODO) processes pending images

## Troubleshooting

### No slides generated

1. Check if teachers have `country` set in their profile
2. Verify there are ClassSessions for tomorrow's date
3. Check `slide_log.txt` for detailed errors

### Schema validation failures

1. Check the AI response in logs
2. Verify response contains valid JSON
3. Check for unknown layouts or extra keys

### Dependencies

```bash
pip install apscheduler pytz pycountry aiohttp pydantic
```
