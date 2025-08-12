import pytz
from rest_framework import serializers
from .models import Message
from django.contrib.auth.models import User



class MessageSerializer(serializers.ModelSerializer):
    timestamp = serializers.SerializerMethodField()
    seen_at = serializers.SerializerMethodField()

    def get_timestamp(self, obj):
        return obj.timestamp.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %I:%M %p")

    def get_seen_at(self, obj):
        return obj.seen_at.astimezone(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %I:%M %p")

    class Meta:
        model = Message
        fields = '__all__'

