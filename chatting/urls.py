from django.urls import path
from .views import ChatMessagesView

urlpatterns = [
    path('<path:room_name>/', ChatMessagesView.as_view(), name='chat'),
]
