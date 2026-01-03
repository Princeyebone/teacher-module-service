# Lesson Brief Scheduler

Automatically generates lesson briefs for teachers around midnight (12:00 AM - 2:00 AM) in their local timezone.

## Files Overview

| File | Purpose |
|------|---------|
| `__init__.py` | Package exports |
| `brief_scheduler.py` | APScheduler setup, hourly trigger |
| `brief_processor.py` | Main logic: timezone check, data fetching, prompt building, AI call |
| `brief_prompts.py` | Prompt template builder for the AI |
| `country_timezone_map.py` | Country → Timezone mapping utility using pytz |
| `run_brief_scheduler.py` | Entry point to start the scheduler |
| `models.py` | SQLModel definition for LessonBrief table |
| `create_lesson_briefs.sql` | SQL script to create the database table |

## Installation

### 1. Install Dependencies

```bash
pip install apscheduler pytz pycountry aiohttp
```

### 2. Create Database Table

Run this in your PostgreSQL terminal:

```bash
psql -U postgres -h localhost -d tmdl5 -p 5433 -f brief_sche/create_lesson_briefs.sql
```

Or copy the contents of `create_lesson_briefs.sql` and run directly in psql.

## Usage

### Start the Scheduler

```bash
python brief_sche/run_brief_scheduler.py
```

Or as a module:

```bash
python -m brief_sche.run_brief_scheduler
```

### Manual Test Run

You can manually trigger the generation cycle for testing:

```python
import asyncio
from brief_sche.brief_processor import run_brief_generation_cycle

asyncio.run(run_brief_generation_cycle())
```

## How It Works

### Scheduler Flow

1. **Every hour** (at :00), the scheduler triggers the main operation
2. **Fetches all teachers** from the database who have a country set
3. **For each teacher**:
   - Gets their timezone from their country
   - Checks if their local time is in the 12 AM - 2 AM window
   - If NOT in window → Skip
   - If IN window → Proceed to generate briefs

### Brief Generation Flow

For each teacher in the time window:

1. **Get all subject + class combinations** from ClassSession table
2. **For each subject + class**:
   - Find **today's session** (session with today's date)
   - Find **previous session** (most recent session before today)
   - Get **lesson context** (strand, substrand, content standard, indicators) for both sessions
   - Get **weekly activity** from course outline based on week number
   - Build AI prompt with all this context
   - Call AI to generate the brief
   - Save to `lesson_briefs` table (with UPSERT for idempotency)

### Idempotency

The `lesson_briefs` table has a unique constraint on `(teacher_id, subject, class_name, session_date)`. If a brief already exists for that combination, it will be **updated** instead of creating a duplicate.

## Database Schema

```sql
CREATE TABLE lesson_briefs (
    id UUID PRIMARY KEY,
    teacher_id UUID NOT NULL,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    session_date DATE NOT NULL,
    session_id INTEGER,
    previous_session_id INTEGER,
    previous_lesson JSONB,
    todays_lesson JSONB,
    weekly_activity JSONB,
    brief_content TEXT NOT NULL,
    generated_at TIMESTAMP,
    updated_at TIMESTAMP,
    generation_status VARCHAR(20),
    
    UNIQUE(teacher_id, subject, class_name, session_date)
);
```

## Logs

Logs are written to `brief_sche/brief_log.txt`.

## Troubleshooting

### No briefs generated

1. Check if teachers have `country` set in their profile
2. Verify the country name matches our timezone mapping
3. Check if there are ClassSessions for today's date
4. Review `brief_log.txt` for detailed errors

### Timezone issues

Run the timezone test:

```python
from brief_sche.country_timezone_map import get_timezone_for_country

print(get_timezone_for_country("Ghana"))  # Should print: Africa/Accra
```

### Missing dependencies

```bash
pip install apscheduler pytz pycountry aiohttp
```
