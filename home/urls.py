from django.urls import path
from .views import coursesView , QuePdfView


urlpatterns = [
    path('courses/', coursesView.as_view(), name='courses'),
    path('QuePdf/', QuePdfView.as_view(), name='QuePdf'),
]