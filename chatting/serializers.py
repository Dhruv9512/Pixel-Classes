import pytz
from rest_framework import serializers
from .models import Message
from django.contrib.auth.models import User



class MessageSerializer(serializers.ModelSerializer):

    class Meta:
        model = Message
        fields = '__all__'

