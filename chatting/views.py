from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.db.models import Q
from urllib.parse import unquote
from .models import Message
from .serializers import MessageSerializer


class ChatMessagesView(APIView):
    def get(self, request, room_name):
        try:
            username1_enc, username2_enc = room_name.split('__')
            username1 = unquote(username1_enc)
            username2 = unquote(username2_enc)

            user1 = User.objects.get(username=username1)
            user2 = User.objects.get(username=username2)

            messages = Message.objects.filter(
                Q(sender=user1, receiver=user2) | Q(sender=user2, receiver=user1)
            ).order_by('timestamp')

            serializer = MessageSerializer(messages, many=True)
            return Response(serializer.data)

        except User.DoesNotExist:
            return Response({"error": "One or both users not found"}, status=404)
        except ValueError:
            return Response({"error": "Invalid room name format. Use 'user1__user2'"}, status=400)
