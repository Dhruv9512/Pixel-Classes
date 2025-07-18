from rest_framework import serializers
from .models import profile
from rest_framework import serializers
from Profile.models import profile as ProfileModel
from urllib.parse import unquote
from home.models import AnsPdf


# Serializer for the profile model
class profileSerializer(serializers.ModelSerializer):

    class Meta:
        model = profile
        fields = ['id' , 'user_obj' , 'profile_pic']
    
    def create(self, validated_data):
        return profile.objects.create(**validated_data) 


# Serializer for user posts (if needed in the future)
class UserPostsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnsPdf 
        fields = ['id', 'que_pdf', 'name', 'contant', 'pdf']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = profile
        fields = ['profile_pic']