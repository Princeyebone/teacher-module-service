# celery_app.py
from celery import Celery

celery_app = Celery(
    "teacher_scheduler",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# ✅ Since everything is in the same directory, just use the file name (no package)


celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Accra",
    enable_utc=True,
)


import background