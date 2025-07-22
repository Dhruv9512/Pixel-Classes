from rest_framework import serializers
from django.contrib.auth.models import User
from Profile.models import profile
# Serializer for Login
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, required=True)


# Serializer for Register
class RegisterSerializer(serializers.ModelSerializer):
    profile_pic = serializers.CharField(required=False, write_only=True)

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

    def create(self, validated_data):
        # Extract profile_pic (use default if not provided)
        profile_pic = validated_data.pop('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
        course = validated_data.pop('course', "B.C.A")

        # Create the User (without setting password)
        user = User.objects.create(**validated_data)

        # Create associated profile
        profile.objects.create(user_obj=user, profile_pic=profile_pic, course=course)

        return user


class ManualRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    course = serializers.CharField(required=False, default="B.C.A")
    profile_pic = serializers.CharField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'course', 'profile_pic']

    def create(self, validated_data):
        course = validated_data.pop('course', "B.C.A")
        profile_pic = validated_data.pop('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
        
        # Create user and hash password
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            is_active=False  # Inactive until email verification
        )

        # Create profile for user
        profile.objects.create(
            user_obj=user,
            course=course,
            profile_pic=profile_pic
        )

        return user


class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6)


# Serializer to validate the incoming data
class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

