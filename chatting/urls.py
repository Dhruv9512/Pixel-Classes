from django.urls import path
from .views import ChatMessagesView

urlpatterns = [
    path('<str:room_name>/', ChatMessagesView.as_view(), name='chat'),
]
