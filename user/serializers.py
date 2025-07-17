from rest_framework import serializers
from django.contrib.auth.models import User
from Profile.models import profile as ProfileModel
# Serializer for Login
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(max_length=128, required=True)


# Serializer for Register
class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password','id']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        ProfileModel.objects.create(
            user_obj=user,
            profile_pic=validated_data.get('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
        )
        user.is_active = False
        user.save()
        return user
    
class OTPSerializer(serializers.Serializer):
    otp = serializers.CharField(min_length=6, max_length=6)


# Serializer to validate the incoming data
class PasswordResetSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)

