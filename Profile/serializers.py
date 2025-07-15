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


# Combined serializer for user and profile details
class CombinedProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user_obj.username')
    email = serializers.EmailField(source='user_obj.email')
    joined_date = serializers.DateTimeField(source='user_obj.date_joined', format='%Y-%m-%d')
    profile_pic = serializers.SerializerMethodField()

    class Meta:
        model = ProfileModel
        fields = ['username', 'email', 'joined_date', 'profile_pic']

    def get_profile_pic(self, obj):
        pic_name = obj.profile_pic.name
        if pic_name.startswith('http') or pic_name.startswith('https'):
            return unquote(pic_name)
        try:
            return obj.profile_pic.url
        except:
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