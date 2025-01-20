from django.urls import path
from .views import CourseList


urlpatterns = [
    path('CourseList/', CourseList.as_view(), name='CourseList'),
]