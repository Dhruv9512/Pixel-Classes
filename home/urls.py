from django.urls import path
from .views import CoursesView , QuePdfView , AnsPdfUploadView, AnsPdfView , QuePdfSubView , QuePdfGetSubView , QuePdfAddView , CacheCleanupView


urlpatterns = [
    path('courses/', CoursesView.as_view(), name='courses'),
    path('QuePdf/', QuePdfView.as_view(), name='QuePdf'),
    path('upload_pdf/', AnsPdfUploadView.as_view(), name='upload_pdf'),
    path('AnsPdf/', AnsPdfView.as_view(), name='upload_pdf'),
    path('QuePdf/Subject_Pdf', QuePdfSubView.as_view(), name='QuePdf_Subject_Pdf'),
    path('QuePdf/Get_Subjact', QuePdfGetSubView.as_view(), name='QuePdf_Get_Subjact'),
    path('QuePdf/Add/', QuePdfAddView.as_view(), name='Quepdf_Add'),
    path('cache/cleanup/', CacheCleanupView.as_view(), name='cache_cleanup')
]   