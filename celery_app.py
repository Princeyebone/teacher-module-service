# celery_app.py
from celery import Celery
from config import settings

celery_app = Celery(
    "teacher_scheduler",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.task_track_started = True
celery_app.conf.result_expires = 3600  # 1 hour
# ✅ Since everything is in the same directory, just use the file name (no package)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Accra",
    enable_utc=True,
)


import background

from celery.result import AsyncResult

result = AsyncResult("0b91a127-3967-4c87-b016-6ad4916acf55", app=celery_app)
print(result.status)  # e.g., "SUCCESS"
