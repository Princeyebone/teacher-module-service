# 🔄 ARQ Task Queue Workflow - TMDL5 System

## 📊 **System Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Redis Queue   │    │   ARQ Worker    │
│   (main.py)     │    │   (Broker)      │    │ (background.py) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │
         │ 1. Enqueue Task        │                        │
         ├───────────────────────►│                        │
         │                        │ 2. Job Available       │
         │                        ├───────────────────────►│
         │                        │                        │
         │ 3. WebSocket Updates   │ 4. Progress Updates    │
         │◄───────────────────────┤◄───────────────────────┤
         │                        │                        │
         │ 5. Task Complete       │                        │
         │◄───────────────────────┴────────────────────────┤
```

## 🎯 **Main Task: Schedule Generation**

### **Purpose:**
The [`generate_schedule_task`](file://c:\Users\HP\tmdl5\background.py#L267) creates intelligent academic schedules by:
- Processing teacher timetables and academic calendars
- Fetching real holidays using AI services
- Generating filtered class sessions
- Creating academic milestones and events

### **Input Parameters:**
- `teacher_id`: UUID of the teacher
- `country`: Country for holiday fetching (e.g., "Ghana")

## 🔄 **Complete Workflow**

### **Phase 1: Task Initiation**
```python
# 1. User Action (Frontend/API)
POST /api/generate-schedule
{
  "teacher_id": "uuid-string",
  "country": "Ghana"
}

# 2. FastAPI Route Handler
from enque_task import enqueue_schedule_generation
job_id = await enqueue_schedule_generation(teacher_id, country)

# 3. Task Queued in Redis
# ARQ stores the task with parameters and metadata
```

### **Phase 2: Worker Processing**
```python
# 4. ARQ Worker picks up the task
async def generate_schedule_task(ctx, teacher_id: str, country: str):
    
    # 5. Initial WebSocket notification
    await publish_ws_message(teacher_id, {
        "status": "started",
        "message": "Generating schedule..."
    })
    
    # 6. Database queries
    calendar = await session.execute(
        select(AcademicCalendar).where(teacher_id == teacher_id)
    )
    timetable = await session.execute(
        select(WeeklyTimeTable).where(teacher_id == teacher_id)
    )
    
    # 7. AI Holiday Fetch
    holidays = get_holidays_from_ai(country, year)
    
    # 8. Schedule Generation Logic
    sessions = generate_class_dates(start_date, end_date, timetable)
    filtered_sessions = filter_sessions(sessions, events, holidays)
    
    # 9. Database Updates
    for session in filtered_sessions:
        db.add(ClassSession(...))
    await db.commit()
    
    # 10. Completion notification
    await publish_ws_message(teacher_id, {
        "status": "completed",
        "message": f"{len(sessions)} sessions created"
    })
```

### **Phase 3: Real-time Updates**
```python
# 11. WebSocket Broadcasting
# Redis Pub/Sub pattern:
await redis_client.publish(f"ws:{teacher_id}", message)

# 12. WebSocket Manager forwards to client
async def redis_listener():
    async for message in pubsub.listen():
        teacher_id = channel.split(":")[1]
        await send_websocket_message(teacher_id, payload)

# 13. Frontend receives real-time updates
```

## 📈 **Data Flow Diagram**

```
Teacher Upload Timetable
         ↓
Academic Calendar Created  
         ↓
Schedule Generation Triggered ──────┐
         ↓                          │
┌────────────────────────────────────┤
│ ARQ Worker Process                 │
├────────────────────────────────────┤
│ 1. Fetch Academic Data            │ 
│ 2. Get AI Holidays                │
│ 3. Generate Sessions              │
│ 4. Filter by Events/Holidays     │
│ 5. Save to Database               │
│ 6. Create Planner Events          │
└────────────────────────────────────┘
         ↓
Real-time WebSocket Updates
         ↓
Frontend Schedule Display
```

## 🔍 **Task Processing Steps**

### **Step 1: Data Validation**
```python
# Validate teacher exists and has required data
if not calendar:
    raise ValueError("No academic calendar found")
if not timetable:
    raise ValueError("No timetable found")
```

### **Step 2: Session Generation**
```python
# Generate all possible class sessions
def generate_class_dates(start_date, end_date, timetable):
    sessions = []
    for entry in timetable:
        weekday_num = WEEKDAY_MAP[entry.weekday.lower()]
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == weekday_num:
                sessions.append({
                    "subject": entry.subject,
                    "date": current_date,
                    "start_time": entry.start_time,
                    "end_time": entry.end_time,
                    "class_name": entry.pupils,
                    "location": entry.location
                })
            current_date += timedelta(days=1)
    return sessions
```

### **Step 3: Intelligent Filtering**
```python
# Filter out sessions that conflict with:
def filter_sessions(sessions, events, holidays, calendar_data):
    no_class_dates = set()
    
    # Mid-semester breaks
    if calendar_data.get("mid_semester_break_start_date"):
        # Add break dates to no_class_dates
    
    # Academic events (exams, holidays)
    for event in events:
        if event.get("requires_no_classes"):
            # Add event dates to no_class_dates
    
    # AI-fetched national holidays
    for holiday in holidays:
        if holiday.get("requires_no_classes"):
            no_class_dates.add(holiday["date"])
    
    # Filter sessions
    filtered = [s for s in sessions 
               if s["date"].strftime("%Y-%m-%d") not in no_class_dates]
    return filtered
```

### **Step 4: Academic Milestone Creation**
```python
# Create planner events for key dates
milestones = [
    {
        "date": calendar_data["semester_start_date"],
        "title": "Semester Begins",
        "event_type": "academic"
    },
    {
        "date": calendar_data["semester_end_date"],
        "title": "Semester Ends", 
        "event_type": "academic"
    }
]
```

## 📊 **Performance Characteristics**

### **Task Execution Time:**
- **Small timetable** (5 subjects): ~10-30 seconds
- **Large timetable** (15+ subjects): ~30-90 seconds
- **AI holiday fetch**: ~5-15 seconds (with timeout)

### **Resource Usage:**
- **Database connections**: Pool managed (max 10 concurrent)
- **Memory**: ~50-100MB per task
- **Redis storage**: Job metadata + progress updates

### **Error Handling:**
- **Database connection failures**: Automatic retry with exponential backoff
- **AI service timeouts**: Fallback to empty holiday list
- **Invalid data**: Task fails with detailed error message

## 🎛️ **Monitoring and Debugging**

### **Job Status Checking:**
```python
from enque_task import check_job_status

status = await check_job_status(job_id)
print(f"Status: {status['status']}")
print(f"Started: {status['started_at']}")
print(f"Result: {status['result']}")
```

### **WebSocket Message Types:**
```python
# Progress updates sent to frontend
{
    "status": "started|processing|completed|error",
    "message": "Human readable message",
    "teacher_id": "uuid",
    "details": {
        "sessions_saved": 150,
        "holidays_found": 12,
        "events_processed": 8
    }
}
```

### **Logging Levels:**
- **INFO**: Task start/completion, major steps
- **DEBUG**: Detailed processing steps
- **WARNING**: Recoverable errors (AI timeouts)
- **ERROR**: Task failures, database issues

## 🔧 **Configuration Options**

### **Worker Settings:**
```python
worker_config = {
    'max_tries': 5,        # Retry failed tasks
    'retry_delay': 15,     # Seconds between retries
    'job_timeout': 300,    # Max task execution time
    'concurrent_jobs': 2,  # Parallel task processing
}
```

### **Database Settings:**
```python
async_engine = create_async_engine(
    pool_size=10,          # Connection pool size
    max_overflow=20,       # Extra connections under load
    pool_timeout=5,        # Wait time for connection
    pool_recycle=180       # Connection refresh interval
)
```

This workflow ensures reliable, scalable background processing with real-time user feedback and robust error handling!