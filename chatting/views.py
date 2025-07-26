from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Message
from .serializers import MessageSerializer
from django.db.models import Q

class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_name):
        query = request.query_params.get('q')

        messages = Message.objects.filter(room_name=room_name)
        if query:
            messages = messages.filter(Q(content__icontains=query))

        messages = messages.order_by('timestamp')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


