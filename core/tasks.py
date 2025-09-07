from celery import shared_task
from django.core.cache import cache

@shared_task
def clean_expired_cache():
    cache.clear_expired()
