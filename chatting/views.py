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

@method_decorator(never_cache, name="dispatch")
class ChatMessagesView(APIView):
    def get(self, request, room_name):
        query = request.query_params.get('q')

        try:
            # Correctly decode the usernames
            username1_enc, username2_enc = room_name.split('__')
            username1 = unquote(username1_enc)
            username2 = unquote(username2_enc)

            # Get the user objects
            try:
                user1 = User.objects.get(username=username1)
            except User.DoesNotExist:
                return Response({"error": f"User '{username1}' not found"}, status=404)

            try:
                user2 = User.objects.get(username=username2)
            except User.DoesNotExist:
                return Response({"error": f"User '{username2}' not found"}, status=404)


            # Filter messages where (sender=user1 AND receiver=user2) OR vice versa
            messages = Message.objects.filter(
                Q(sender=user1, receiver=user2) | Q(sender=user2, receiver=user1)
            )

            # Optional text search
            if query:
                messages = messages.filter(content__icontains=query)

            messages = messages.order_by('timestamp')

            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response({"error": "One or both users not found"}, status=404)

        except ValueError:
            return Response({"error": "Invalid room name format. Use 'user1__user2'"}, status=400)
        

@method_decorator(never_cache, name="dispatch")
class EditMessageView(APIView):
    
    permission_classes = [IsAuthenticated]
    def put(self, request, pk):
        try:
            message = Message.objects.get(pk=pk)
            sender = request.user
            # Only sender can edit their message
            if message.sender != sender:
                return Response(
                    {"error": "You can only edit your own messages"},
                    status=status.HTTP_403_FORBIDDEN
                )

            new_content = request.data.get("content")
            if not new_content:
                return Response({"error": "Content is required"}, status=400)

            message.content = new_content
            message.save()


            # Broadcast edit to WebSocket group
            channel_layer = get_channel_layer()
            room_name = f"{message.sender.username}__{message.receiver.username}"  # your room_name logic
            group_name = f"chat_{hashlib.sha256(room_name.encode()).hexdigest()}"
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "edit_message",   # triggers edit_message method in ChatConsumer
                    "id": message.id,
                    "new_content": new_content
                }
            )
            serializer = MessageSerializer(message)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)
        

@method_decorator(never_cache, name="dispatch")
class DeleteMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            message = Message.objects.get(pk=pk)
            sender = request.user
            # Only sender can delete their message
            if message.sender != sender:
                return Response(
                    {"error": "You can only delete your own messages"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            room_name = f"{message.sender.username}__{message.receiver.username}"
            group_name = f"chat_{hashlib.sha256(room_name.encode()).hexdigest()}"

            message.delete()
            # Broadcast delete to WebSocket group
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "delete_message",  # triggers delete_message method in ChatConsumer
                    "id": message.id
                }
            )
            return Response({"message": "Message deleted successfully"}, status=status.HTTP_200_OK)

        except Message.DoesNotExist:
            return Response({"error": "Message not found"}, status=status.HTTP_404_NOT_FOUND)
