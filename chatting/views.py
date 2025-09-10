import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q
from urllib.parse import unquote
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import hashlib
from user.authentication import CookieJWTAuthentication
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# per room cach

@method_decorator(never_cache, name="dispatch")
class ChatMessagesView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, room_name):
        query = request.query_params.get("q")
        sender = request.user   # ✅ sender from JWT
        logger.info(f"[ChatMessagesView] sender={sender.username}, room_name={room_name}, query={query}")

        try:
            # Receiver from URL (room_name = receiver username)
            receiver = User.objects.get(username=room_name)
            logger.info(f"[ChatMessagesView] Receiver resolved: {receiver.username}")

            # Cache key
            cache_key = f"chat_messages:{sender.username}__{receiver.username}:{query or ''}"
            cached = cache.get(cache_key)
            if cached:
                logger.debug(f"[ChatMessagesView] Cache hit for {cache_key}")
                return Response(cached)

            # Query DB for messages between sender & receiver
            messages = Message.objects.filter(
                Q(sender=sender, receiver=receiver) | Q(sender=receiver, receiver=sender)
            )
            if query:
                messages = messages.filter(content__icontains=query)

            messages = messages.order_by("timestamp")
            serializer = MessageSerializer(messages, many=True)

            # Cache for 5 min
            cache.set(cache_key, serializer.data, timeout=300)
            logger.debug(f"[ChatMessagesView] Cache set for {cache_key}")

            return Response(serializer.data)

        except User.DoesNotExist:
            logger.error("[ChatMessagesView] Receiver not found")
            return Response({"error": "Receiver not found"}, status=404)

@method_decorator(never_cache, name="dispatch")
class EditMessageView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        sender = request.user
        if not sender:
            logger.warning("Invalid token")
            return Response({"error": "Invalid token"}, status=401)

        try:
            message = Message.objects.get(pk=pk)
            logger.info(f"Message found: {message.id} by {message.sender.username}")
        except Message.DoesNotExist:
            logger.error("Message not found")
            return Response({"error": "Message not found"}, status=404)

        if message.sender != sender:
            logger.warning("User tried to edit someone else's message")
            return Response({"error": "You can only edit your own messages"}, status=403)

        new_content = request.data.get("content")
        if not new_content:
            logger.warning("No new content provided")
            return Response({"error": "Content is required"}, status=400)

        message.content = new_content
        message.save()
        logger.info(f"Message {message.id} updated")

        channel_layer = get_channel_layer()
        room_name = f"{message.sender.username}__{message.receiver.username}"
        group_name = f"chat_{hashlib.sha256(room_name.encode()).hexdigest()}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "edit_message", "id": message.id, "new_content": new_content}
        )
        logger.info(f"Edit broadcasted to group {group_name}")

        return Response({"id": message.id, "content": message.content}, status=200)


@method_decorator(never_cache, name="dispatch")
class DeleteMessageView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def delete(self, request, pk):
        sender = request.user
        if not sender:
            logger.warning("Invalid token")
            return Response({"error": "Invalid token"}, status=401)

        try:
            message = Message.objects.get(pk=pk)
            logger.info(f"Message found: {message.id} by {message.sender.username}")
        except Message.DoesNotExist:
            logger.error("Message not found")
            return Response({"error": "Message not found"}, status=404)

        if message.sender != sender:
            logger.warning("User tried to delete someone else's message")
            return Response({"error": "You can only delete your own messages"}, status=403)

        room_name = f"{message.sender.username}__{message.receiver.username}"
        group_name = f"chat_{hashlib.sha256(room_name.encode()).hexdigest()}"

        message.delete()
        logger.info(f"Message {pk} deleted")

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "delete_message", "id": pk}
        )
        logger.info(f"Delete broadcasted to group {group_name}")

        return Response({"message": "Message deleted successfully"}, status=200)
