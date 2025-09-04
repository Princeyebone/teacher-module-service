# Background Processing Organization

This document describes the reorganization of background processing files into dedicated folders for better maintainability and clarity.

## Folder Structure

### 📅 `sch_ground/` - Schedule Background Processing
Contains all background task processing related to **schedule generation**, academic calendar operations, and intelligent class session creation.

**Files:**
- `background.py` - Main schedule generation tasks and worker configuration
- `arq_worker.py` - ARQ worker startup and management utilities  
- `worker_manager.py` - Production worker management for scaling
- `__init__.py` - Package initialization

**Usage:**
```python
# Import schedule generation functions
from sch_ground.background import generate_schedule_task, arq_redis_settings

# Start ARQ worker for schedule processing
from sch_ground.arq_worker import start_worker
await start_worker()

# Manage multiple workers in production
from sch_ground.worker_manager import WorkerManager
manager = WorkerManager(num_workers=3)
manager.start_workers()
```

### 📄 `t_ground/` - Timetable Background Processing  
Contains all background task processing related to **timetable file uploads**, text extraction, and file processing operations.

**Files:**
- `table_back.py` - Timetable file processing tasks and text extraction
- `run_timetable_worker.py` - Dedicated timetable worker runner
- `__init__.py` - Package initialization

**Usage:**
```python
# Import timetable processing functions
from t_ground.table_back import process_timetable_file_task, FileExtractor

# Start dedicated timetable worker
python t_ground/run_timetable_worker.py

# Or use ARQ directly
python -m arq t_ground.table_back.timetable_worker_config
```

### 🔗 Shared Components
- `enque_task.py` - Remains in root directory, contains both schedule and timetable task enqueueing functions
- `websocket_manager.py` - Handles real-time communication for both types of tasks

## Running Workers

### Development
```bash
# Option 1: Use convenient runner from root directory
python run_schedule_worker.py         # Start worker
python run_schedule_worker.py info     # Show configuration
python run_schedule_worker.py test     # Test Redis connection

# Option 2: Direct ARQ command
python -m arq sch_ground.background.worker_config

# Option 3: Run from sch_ground directory
cd sch_ground
python arq_worker.py

# Start timetable processing worker  
python t_ground/run_timetable_worker.py
```

### Production
```bash
# Start multiple schedule workers
python sch_ground/worker_manager.py start -n 3

# Start dedicated timetable worker
python t_ground/run_timetable_worker.py
```

## Import Path Changes

All imports have been updated to reflect the new structure:

**Before:**
```python
from background import arq_redis_settings
from table_back import process_timetable_file_task
```

**After:**
```python
from sch_ground.background import arq_redis_settings
from t_ground.table_back import process_timetable_file_task
```

## Benefits

1. **Clear Separation** - Schedule and timetable processing are now clearly separated
2. **Better Organization** - Related files are grouped together
3. **Easier Maintenance** - Each folder has a specific purpose and scope
4. **Scalable Architecture** - Can run different workers independently
5. **Documentation** - Each package has clear documentation of its purpose

## Migration Notes

- All existing APIs continue to work without changes
- Import paths have been updated throughout the codebase
- Both worker types can run independently or together
- No database schema changes required
- Configuration files remain in root directory