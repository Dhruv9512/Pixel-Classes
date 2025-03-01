from django.urls import path
from .views import CoursesView , QuePdfView , AnsPdfUploadView


urlpatterns = [
    path('courses/', CoursesView.as_view(), name='courses'),
    path('QuePdf/', QuePdfView.as_view(), name='QuePdf'),
    path('upload_pdf/', AnsPdfUploadView.as_view(), name='upload_pdf'),
]