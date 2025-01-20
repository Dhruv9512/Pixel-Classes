from django.urls import path
from .views import CourseList


urlpatterns = [
    path('login/', CourseList.as_view(), name='CourseList'),
]