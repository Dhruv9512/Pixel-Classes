from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer
from django.db.models import Q
from django.contrib.auth.models import User
from urllib.parse import unquote

class ChatMessagesView(APIView):
   
    def get(self, request, room_name):
        query = request.query_params.get('q')

        try:
            username1, username2 = map(unquote, room_name.split('__'))
            unquote(username1), unquote(username2) = room_name.split('__')

            # Get the user objects
            user1 = User.objects.get(username=username1)
            user2 = User.objects.get(username=username2)

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

