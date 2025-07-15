from django.urls import path
from .views import ProfileDetailsView

urlpatterns = [
    path('details/', ProfileDetailsView.as_view(),name='profile_details'),
]   