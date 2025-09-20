from rest_framework import serializers
from .models import Message

class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.CharField(source='sender.username', read_only=True)
    receiver = serializers.CharField(source='receiver.username', read_only=True)
    timestamp = serializers.DateTimeField(read_only=True)  # explicit type helps DRF pipeline [web:75]

    class Meta:
        model = Message
        fields = [
            'id',
            'sender',
            'receiver',
            'content',
            'timestamp',
            'is_seen',
            'seen_at'
        ]
        read_only_fields = ['id', 'sender', 'receiver', 'timestamp', 'is_seen', 'seen_at']  # faster as read-only where applicable [web:131]
