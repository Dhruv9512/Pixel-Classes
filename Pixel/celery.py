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

