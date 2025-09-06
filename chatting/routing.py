from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # New user-level notification consumer
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    # Existing chat room consumer
    re_path(r'ws/chat/(?P<room_name>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
]
