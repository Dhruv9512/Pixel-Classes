from django.urls import path
from .views import ExpiredCleanupView

urlpatterns = [
    path('expiry-cleanup/', ExpiredCleanupView.as_view(), name='cache_cleanup')
]   