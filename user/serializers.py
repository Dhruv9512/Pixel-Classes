from rest_framework import serializers
from django.contrib.auth.models import User
from Profile.models import profile, Follow

# Serializer for Login
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True, trim_whitespace=True)
    password = serializers.CharField(max_length=128, required=True, write_only=True)

# Serializer for Register (OAuth/auto flow; does not set password)
class RegisterSerializer(serializers.ModelSerializer):
    # profile_pic is write-only input; default handled in create
    profile_pic = serializers.CharField(required=False, write_only=True, allow_blank=True)
    # optionally accept course though not in Meta fields; injected in create
    # course is accepted via validated_data.pop in create

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'profile_pic',
        ]
        read_only_fields = ['id']

    def create(self, validated_data):
        # Defaults (unchanged behavior)
        profile_pic = validated_data.pop('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
        course = validated_data.pop('course', "B.C.A")

        # Create the User (no password set here by design)
        # Use create to avoid extra work; fields are already validated. [web:27]
        user = User.objects.create(**validated_data)

        # Create associated profile and follow rows
        profile.objects.create(user_obj=user, profile_pic=profile_pic, course=course)
        Follow.objects.create(user=user)
        return user

class ManualRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    course = serializers.CharField(required=False, default="B.C.A", allow_blank=False)
    profile_pic = serializers.CharField(required=False, default="https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp", allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'course', 'profile_pic']

    def create(self, validated_data):
        # Pop non-User fields with defaults (same logic)
        course = validated_data.pop('course', "B.C.A")
        profile_pic = validated_data.pop('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")

        # Create user and hash password (create_user handles hashing). [web:83][web:86]
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False  # Inactive until email verification
        )

        # Create profile and follow records
        profile.objects.create(user_obj=user, course=course, profile_pic=profile_pic)
        Follow.objects.create(user=user)
        return user

class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6, trim_whitespace=True)

class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6, write_only=True)
