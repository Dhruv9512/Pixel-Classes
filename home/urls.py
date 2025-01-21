from django.urls import path
from .views import courses


urlpatterns = [
    path('courses/', courses.as_view(), name='courses'),
]