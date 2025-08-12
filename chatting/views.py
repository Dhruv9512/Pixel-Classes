from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q
from urllib.parse import unquote

from .models import Message
from .serializers import MessageSerializer

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
