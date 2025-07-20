from rest_framework import serializers
from .models import profile
from rest_framework import serializers
from Profile.models import profile as ProfileModel
from urllib.parse import unquote
from home.models import AnsPdf
from django.contrib.auth.models import User

# Serializer for the profile model
class profileSerializer(serializers.ModelSerializer):

    class Meta:
        model = profile
        fields = ['id' , 'user_obj' , 'profile_pic']
    
    def create(self, validated_data):
        return profile.objects.create(**validated_data) 


# Combined serializer for user and profile details
class CombinedProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user_obj.username')
    email = serializers.EmailField(source='user_obj.email')
    joined_date = serializers.DateTimeField(source='user_obj.date_joined', format='%Y-%m-%d')
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = profile
        fields = ['username', 'email', 'joined_date', 'profile_pic']

    def get_profile_pic(self, obj):
        pic = obj.profile_pic
        if not pic:
            return None
        # If already a URL or path string
        if isinstance(pic, str):
            if pic.startswith('http') or pic.startswith('https'):
                return unquote(pic)
            return pic
        # If it's a FileField/ImageField
        try:
            if pic.name.startswith('http') or pic.name.startswith('https'):
                return unquote(pic.name)
            return pic.url
        except Exception:
            return None


# Serializer for user posts (if needed in the future)
class UserPostsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnsPdf 
        fields = ['id', 'que_pdf', 'name', 'contant', 'pdf']


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = profile
        fields = ['profile_pic']




class UserSearchSerializer(serializers.ModelSerializer):
    profile_pic = serializers.SerializerMethodField()
    joined_date = serializers.DateTimeField(source='date_joined', format='%Y-%m-%d')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'joined_date', 'profile_pic']

    def get_profile_pic(self, obj):
        try:
            profile = ProfileModel.objects.get(user_obj=obj)
            return profile.profile_pic if profile.profile_pic else None
        except ProfileModel.DoesNotExist:
            return None



