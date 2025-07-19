from rest_framework import serializers
from django.contrib.auth.models import User
from Profile.models import profile as ProfileModel
# Serializer for Login
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, required=True)


# Serializer for Register
class RegisterSerializer(serializers.ModelSerializer):
    profile_pic = serializers.URLField(required=False, write_only=True)

    class Meta:
        model = User
        fields = [
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
        ]
    
    def create(self, validated_data):
        # Extract profile pic
        profile_pic = validated_data.pop('profile_pic', "https://default.pic.url/here.webp")

        # Create user without password
        user = User(**validated_data)
        user.save()

        # Create user profile
        ProfileModel.objects.create(user_obj=user, profile_pic=profile_pic)

        return user

    
class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6)


# Serializer to validate the incoming data
class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

