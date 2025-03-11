from django.urls import path
from .views import CoursesView , QuePdfView , AnsPdfUploadView, AnsPdfView , QuePdfSubView


urlpatterns = [
    path('courses/', CoursesView.as_view(), name='courses'),
    path('QuePdf/', QuePdfView.as_view(), name='QuePdf'),
    path('upload_pdf/', AnsPdfUploadView.as_view(), name='upload_pdf'),
    path('AnsPdf/', AnsPdfView.as_view(), name='upload_pdf'),
    path('QuePdf/Sub', QuePdfSubView.as_view(), name='QuePdf_Sub'),
]