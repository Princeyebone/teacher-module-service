# ARQ Worker Setup and Usage Guide

## 🔧 Prerequisites

1. **Redis Server Running**
   ```bash
   # Start Redis (Windows)
   redis-server
   
   # Or if using Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Environment Setup**
   ```bash
   # Activate virtual environment
   env\Scripts\activate  # Windows
   
   # Install dependencies
   pip install arq redis
   ```

3. **Database Running**
   - Ensure PostgreSQL is running
   - Database URL configured in `.env`

## 🚀 Running the Worker

### Method 1: Direct ARQ Command (Recommended)
```bash
# From project root directory
python -m arq background.worker_config
```

### Method 2: Using our custom wrapper
```bash
# Start worker
python arq_worker.py start

# Test Redis connection
python arq_worker.py test

# Show configuration info
python arq_worker.py info

# Enqueue test task
python arq_worker.py enqueue
```

### Method 3: Programmatically
```python
import asyncio
from sch_ground.arq_worker import start_worker

# In async context
await start_worker()
```

## 📊 Worker Monitoring

### Check Worker Status
```bash
# The worker will show logs like:
# 🚀 Starting ARQ Worker for TMDL5...
# 📋 Available tasks:
#    - generate_schedule_task
# ✅ Redis connection successful
# 🔄 Worker started, waiting for jobs...
```

### Monitor Tasks
```python
from arq import create_pool
from sch_ground.background import arq_redis_settings

async def check_job_status(job_id):
    redis = await create_pool(arq_redis_settings)
    job = await redis.get_job(job_id)
    print(f"Job {job_id}: {job.status}")
    await redis.aclose()
```

## 🐛 Troubleshooting

### Common Issues:

1. **Redis Connection Failed**
   ```
   ❌ Redis connection failed: [Errno 10061] No connection could be made
   ```
   **Solution:** Start Redis server first

2. **Database Connection Issues**
   ```
   ERROR: Connection to database failed
   ```
   **Solution:** Check DATABASE_URL in .env file

3. **Import Errors**
   ```
   ModuleNotFoundError: No module named 'arq'
   ```
   **Solution:** `pip install arq redis`

### Debug Mode
```bash
# Run with verbose logging
python -m arq background.worker_config --verbose
```

## 🔄 Production Deployment

### Using Process Manager (PM2)
```bash
# Install PM2
npm install -g pm2

# Create ecosystem file
cat > ecosystem.config.js << EOF
module.exports = {
  apps: [{
    name: 'arq-worker',
    script: 'python',
    args: ['-m', 'arq', 'background.worker_config'],
    cwd: '/path/to/tmdl5',
    instances: 2,
    exec_mode: 'fork',
    env: {
      NODE_ENV: 'production'
    }
  }]
};
EOF

# Start workers
pm2 start ecosystem.config.js
```

### Using Systemd (Linux)
```bash
# Create service file
sudo nano /etc/systemd/system/tmdl5-worker.service

[Unit]
Description=TMDL5 ARQ Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/tmdl5
Environment=PATH=/path/to/tmdl5/env/bin
ExecStart=/path/to/tmdl5/env/bin/python -m arq background.worker_config
Restart=always

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable tmdl5-worker
sudo systemctl start tmdl5-worker
```

## 📈 Performance Tuning

### Worker Configuration
```python
# In background.py worker_config
worker_config = {
    'functions': [generate_schedule_task],
    'redis_settings': arq_redis_settings,
    'max_tries': 5,           # Retry failed tasks 5 times
    'retry_delay': 15,        # Wait 15 seconds between retries
    'job_timeout': 300,       # Kill jobs after 5 minutes
    'concurrent_jobs': 2,     # Run 2 jobs simultaneously
    'keep_result': 3600,      # Keep results for 1 hour
}
```

### Multiple Workers
```bash
# Start multiple worker instances
python -m arq background.worker_config &
python -m arq background.worker_config &
python -m arq background.worker_config &
```