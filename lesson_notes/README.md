# Weekly Lesson Notes Module

## Overview

This module automatically generates weekly lesson notes for teachers. It runs on a schedule and creates detailed lesson plans for each indicator in the upcoming week.

## Schedule

- **Runs**: Every hour (at minute 0)
- **Window**: Wednesday 12 AM - 2 AM OR Thursday 12 AM - 2 AM (teacher's local time)
- **Timezone**: Determined by the `country` field in `teacherprofile` table

## How It Works

1. **Hourly Check**: The scheduler runs every hour
2. **Timezone Check**: For each teacher, check if their local time is in the Wed/Thu 12-2 AM window
3. **Subject/Class Loop**: For each subject+class combination the teacher has
4. **Indicator Detection**: Find indicators with sessions in the coming week
5. **AI Generation**: Generate performance indicators, core competencies, and learner activities
6. **Database Save**: Save the lesson note with UPSERT for idempotency

## Lesson Note Structure

### Header Fields
| Field | Description |
|-------|-------------|
| week_date | Friday of the current week |
| subject | Subject name |
| class_name | Class name |
| duration | From weekly timetable (start_time - end_time) |
| strand | Curriculum strand |
| substrand | Curriculum substrand |
| content_standard | Content standard text |
| indicator_text | Learning indicator |
| week_number | Calculated from semester start |
| semester_name | From academic calendar |
| lesson_number | e.g., "1 of 3" (indicator X of total) |
| performance_indicator | AI-generated |
| core_competency | AI-generated |
| reference_page | "{subject} curriculum" |

### Phase Activities (3 Phases)
| Phase | Description |
|-------|-------------|
| Phase 1: Starter | Warm-up activities, prior knowledge activation |
| Phase 2: New Learning | Main instructional content, examples, practice |
| Phase 3: Reflection | Summary, peer discussion, assessment |

## Files

| File | Description |
|------|-------------|
| `__init__.py` | Module initialization and exports |
| `create_weekly_lesson_notes.sql` | SQL to create the database table |
| `note_scheduler.py` | APScheduler configuration |
| `note_processor.py` | Main processing logic with retry mechanism |
| `note_prompts.py` | AI prompt builders and response parsers |
| `test_note_generation.py` | Test script (runs immediately) |
| `README.md` | This documentation |

## Database Table

```sql
CREATE TABLE weekly_lesson_notes (
    id UUID PRIMARY KEY,
    teacher_id UUID NOT NULL,
    subject VARCHAR(255) NOT NULL,
    class_name VARCHAR(255) NOT NULL,
    indicator_id INT,
    week_date DATE NOT NULL,
    -- ... (see create_weekly_lesson_notes.sql for full schema)
    CONSTRAINT unique_weekly_lesson_note 
        UNIQUE(teacher_id, subject, class_name, indicator_id, week_date)
);
```

## Retry Mechanism

All AI and database operations use exponential backoff retry:

- **Initial delay**: 2 seconds
- **Max retries**: 5
- **Backoff multiplier**: 2x
- **Max delay**: 60 seconds

### Retryable Errors
- Network errors (connection, timeout)
- Rate limiting (429)
- Server errors (500, 503)
- Authentication/token errors
- Database errors (deadlock, connection)

## Usage

### Run the Scheduler
```bash
python -m lesson_notes.note_scheduler
```

### Run Test (Immediate, ignores time window)
```bash
python lesson_notes/test_note_generation.py
```

### Create Database Table
```sql
\i lesson_notes/create_weekly_lesson_notes.sql
```

## Dependencies

- APScheduler
- aiohttp
- pytz
- google-auth (for Vertex AI)
- SQLAlchemy (async)

## Configuration

Uses the same configuration as other modules:
- `settings.GCS_SERVICE_ACCOUNT_JSON_VERTEX_AI` - Vertex AI credentials
- `settings.GCS_PROJECT_ID` - Google Cloud project ID
- `settings.DATABASE_URL` - PostgreSQL connection string
