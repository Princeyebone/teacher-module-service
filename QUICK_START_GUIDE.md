# 🚀 Quick Start Guide - TMDL5 Project

*Don't feel overwhelmed! This guide makes everything simple.*

## 📁 What's What? (Simple Version)

```
tmdl5/
├── 🏠 Main App
│   ├── main.py              # The main FastAPI server
│   ├── model.py             # Database tables
│   └── dependencies.py      # User authentication
│
├── 📂 file_handler/         # File upload handlers
│   ├── tm_file_handler.py   # Timetable uploads
│   ├── ca_file_handler.py   # Calendar uploads
│   └── sem_file_handler.py  # Semester mapping
│
├── 📂 sch_ground/           # Schedule background tasks
│   ├── background.py        # Main schedule generator
│   └── arq_worker.py        # Worker to run schedules
│
├── 📂 t_ground/             # Timetable background tasks
│   ├── table_back.py        # Timetable file processor
│   └── run_timetable_worker.py  # Worker for timetables
│
└── 🛠️ Helper Files
    ├── enque_task.py        # Queue background jobs
    ├── websocket_manager.py # Real-time updates
    └── run_schedule_worker.py  # Easy schedule worker
```

## 🎯 Most Important Commands (Just These!)

### Start the Main App
```bash
python main.py
# OR
uvicorn main:app --reload
```

### Start Background Workers (Pick One)
```bash
# For schedule generation (easy way)
python run_schedule_worker.py

# For timetable processing
python t_ground/run_timetable_worker.py
```

### Test if Everything Works
```bash
# Test schedule worker
python run_schedule_worker.py test

# Check what's running
python run_schedule_worker.py info
```

## 🔧 What Each Thing Does (Simple)

| What | What It Does |
|------|-------------|
| **main.py** | The web server that handles all API requests |
| **file_handler/** | Handles when users upload files |
| **sch_ground/** | Creates class schedules in the background |
| **t_ground/** | Processes uploaded timetable files |
| **enque_task.py** | Puts jobs in a queue to run later |
| **websocket_manager.py** | Sends live updates to users |

## 🚦 Daily Workflow (Keep It Simple)

### For Development:
1. **Start the main app**: `python main.py`
2. **Start one worker**: `python run_schedule_worker.py`
3. **That's it!** Your app is running.

### When Something Breaks:
1. **Check if Redis is running**: `python run_schedule_worker.py test`
2. **Check worker status**: `python run_schedule_worker.py info`
3. **Restart everything**: Stop and start again

## 🆘 Common Issues (Easy Fixes)

| Problem | Quick Fix |
|---------|-----------|
| Import errors | Run from the main project folder |
| Redis connection failed | Start Redis: `redis-server` |
| Worker won't start | Check: `python run_schedule_worker.py test` |
| Can't find files | Make sure you're in the `tmdl5` folder |

## 🎯 Focus on These Files Only

**If you're just starting, only worry about:**
1. `main.py` - The main app
2. `run_schedule_worker.py` - Background tasks
3. `file_handler/tm_file_handler.py` - File uploads

**Ignore everything else for now!**

## 📞 Quick Commands Cheat Sheet

```bash
# Start everything you need
python main.py                    # Main app
python run_schedule_worker.py     # Background worker

# Check if things work
python run_schedule_worker.py test    # Test connection
python run_schedule_worker.py info    # Show settings

# Stop everything
Ctrl+C  # In each terminal
```

## 💡 Pro Tips

1. **One terminal for main app, one for worker** - That's all you need
2. **Start with just the schedule worker** - Ignore timetable worker for now
3. **Use the `run_schedule_worker.py`** - It's the easiest way
4. **Keep it simple** - Don't try to understand everything at once

---

**Remember: You don't need to understand everything at once. Start with just running the app and one worker!** 🌟