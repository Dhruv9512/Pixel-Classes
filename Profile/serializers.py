from rest_framework import serializers
from .models import profile
from Profile.models import profile as ProfileModel
from urllib.parse import unquote
from home.models import AnsPdf
from django.contrib.auth.models import User

# Serializer for the profile model
class profileSerializer(serializers.ModelSerializer):
    class Meta:
        model = profile
        fields = ['id', 'user_obj', 'profile_pic']
        read_only_fields = ['id']

    def create(self, validated_data):
        # Direct create (no extra logic)
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
        # If it's already a string path or URL
        if isinstance(pic, str):
            return unquote(pic) if pic.startswith(('http', 'https')) else pic
        # If it's a FileField/ImageField-like object
        name = getattr(pic, 'name', '')
        if name.startswith(('http', 'https')):
            return unquote(name)
        url = getattr(pic, 'url', None)
        return url or None

# Serializer for user posts
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
        """
        Avoid per-row queries by accepting a pre-fetched map in context.
        View should pass context['profiles_by_user_id'] = {user_id: profile_obj}
        to prevent N+1. Falls back to a single query if not provided. Behavior unchanged. [web:75][web:80]
        """
        profiles_map = self.context.get('profiles_by_user_id')
        if profiles_map is not None:
            prof = profiles_map.get(obj.id)
            return getattr(prof, 'profile_pic', None) if prof else None

        # Fallback: original behavior (single get per user)
        try:
            prof = ProfileModel.objects.select_related('user_obj').only('profile_pic', 'user_obj').get(user_obj=obj)
            return prof.profile_pic if prof.profile_pic else None
        except ProfileModel.DoesNotExist:
            return None
