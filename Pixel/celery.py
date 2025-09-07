import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Pixel.settings")

app = Celery("Pixel")

# Load settings from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks
app.autodiscover_tasks()

# Schedule tasks
app.conf.beat_schedule = {
    "clear-expired-cache-every-15-minutes": {
        "task": "core.tasks.clean_expired_cache",  # path to your task
        "schedule": crontab(minute="*/15"),          # run every 15 minutes
    },
}
