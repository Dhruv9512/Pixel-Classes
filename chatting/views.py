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
from django.core.cache import cache

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def _chat_cache_key(a_username, b_username, query=""):
    # Normalize usernames in key to avoid duplicates across directions
    if a_username <= b_username:
        u1, u2 = a_username, b_username
    else:
        u1, u2 = b_username, a_username
    return f"chat_messages:{u1}__{u2}:{query or ''}"

@method_decorator(never_cache, name="dispatch")
class ChatMessagesView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, room_name):
        query = request.query_params.get("q")
        sender = request.user
        logger.info(f"[ChatMessagesView] sender={sender.username}, room_name={room_name}, query={query}")

        try:
            # Resolve receiver with minimal columns [web:27]
            receiver = User.objects.only('id', 'username').get(username=room_name)
            logger.info(f"[ChatMessagesView] Receiver resolved: {receiver.username}")

            cache_key = _chat_cache_key(sender.username, receiver.username, query)
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[ChatMessagesView] Cache hit for {cache_key}")
                return Response(cached)

            # Select related sender/receiver to avoid N+1 in serializer if it accesses them [web:216]
            messages = (
                Message.objects
                .filter(Q(sender=sender, receiver=receiver) | Q(sender=receiver, receiver=sender))
                .select_related('sender', 'receiver')
                .order_by("timestamp")
            )
            if query:
                messages = messages.filter(content__icontains=query)

            serializer = MessageSerializer(messages, many=True)

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
            # Load sender/receiver in one query for later key/group building [web:27]
            message = Message.objects.select_related('sender', 'receiver').only(
                'id', 'content', 'sender__username', 'receiver__username', 'sender_id'
            ).get(pk=pk)
            logger.info(f"Message found: {message.id} by {message.sender.username}")
        except Message.DoesNotExist:
            logger.error("Message not found")
            return Response({"error": "Message not found"}, status=404)

        if message.sender_id != sender.id:
            logger.warning("User tried to edit someone else's message")
            return Response({"error": "You can only edit your own messages"}, status=403)

        new_content = request.data.get("content")
        if not new_content:
            logger.warning("No new content provided")
            return Response({"error": "Content is required"}, status=400)

        # Update only changed field [web:27]
        message.content = new_content
        message.save(update_fields=["content"])
        # Invalidate both directional cache keys for all queries (conservative). [web:214]
        cache.delete_pattern(_chat_cache_key(message.sender.username, message.receiver.username, "*")) if hasattr(cache, "delete_pattern") else (
            cache.delete(_chat_cache_key(message.sender.username, message.receiver.username, "")),
            cache.delete(_chat_cache_key(message.sender.username, message.receiver.username, None))
        )

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
            message = Message.objects.select_related('sender', 'receiver').only(
                'id', 'sender__username', 'receiver__username', 'sender_id'
            ).get(pk=pk)
            logger.info(f"Message found: {message.id} by {message.sender.username}")
        except Message.DoesNotExist:
            logger.error("Message not found")
            return Response({"error": "Message not found"}, status=404)

        if message.sender_id != sender.id:
            logger.warning("User tried to delete someone else's message")
            return Response({"error": "You can only delete your own messages"}, status=403)

        room_name = f"{message.sender.username}__{message.receiver.username}"
        group_name = f"chat_{hashlib.sha256(room_name.encode()).hexdigest()}"

        message.delete()
        # Invalidate caches for both directions and any query variants [web:214]
        cache.delete_pattern(_chat_cache_key(message.sender.username, message.receiver.username, "*")) if hasattr(cache, "delete_pattern") else (
            cache.delete(_chat_cache_key(message.sender.username, message.receiver.username, "")),
            cache.delete(_chat_cache_key(message.sender.username, message.receiver.username, None))
        )

        logger.info(f"Message {pk} deleted")

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "delete_message", "id": pk}
        )
        logger.info(f"Delete broadcasted to group {group_name}")

        return Response({"message": "Message deleted successfully"}, status=200)
