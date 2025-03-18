# Pixel/celery.py

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pixel.settings')

app = Celery('Pixel')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Optional: You can also define a simple task for testing
@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')