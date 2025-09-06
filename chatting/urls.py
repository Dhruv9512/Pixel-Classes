from django.urls import path
from .views import ChatMessagesView,EditMessageView,DeleteMessageView

urlpatterns = [
    path('<int:pk>/edit/', EditMessageView.as_view(), name='edit-message'),
    path('<int:pk>/delete/', DeleteMessageView.as_view(), name='delete-message'),
    path('<path:room_name>/', ChatMessagesView.as_view(), name='chat'),
]
