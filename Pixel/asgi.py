import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Pixel.settings')
django.setup()  # ✅ Must be called before importing app code

# Now safe to import app-level modules
import chattting.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chattting.routing.websocket_urlpatterns
        )
    ),
})
