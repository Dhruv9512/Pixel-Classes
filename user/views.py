from django.contrib.auth import authenticate, login
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.core.cache import cache  
import logging
from .utils import send_mail_for_register, send_mail_for_login
# Set up logging
logger = logging.getLogger(__name__)



# Resend OTP View
class ResendOTPView(APIView):
    def post(self, request):
        """Resend OTP to the user's email."""
        username = request.data.get('username')
        
        # Check if email was provided
        if not username:
            return Response({"error": "Username not found in input."}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Retrieve the user based on the provided email
            user = User.objects.get(username=username)
            
            # Send OTP again
            send_mail_for_register(user)
            
            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            # If no user is found with the provided email, return an error message
            return Response({"error": "No user found with this email address."}, status=status.HTTP_404_NOT_FOUND)



# OTP Verification View
class VerifyOTPView(APIView):
    @csrf_exempt
    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"OTP verification failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        otp = serializer.validated_data['otp']
        username = request.data.get('username')
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"error": "No user found."}, status=status.HTTP_404_NOT_FOUND)

        stored_otp = cache.get(f"otp_{user.pk}")

        if stored_otp is None:
            return Response({"error": "OTP expired or not generated."}, status=status.HTTP_400_BAD_REQUEST)

        if otp == stored_otp:
            user.is_active = True
            user.save()
            cache.delete(f"otp_{user.pk}")
            return Response({"message": "Account activated successfully."}, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

# Login View
class LoginView(APIView):
    @csrf_exempt
    def post(self, request):
        """Authenticate and login user, send verification email."""
        try:
            logger.debug(f"Login attempt for data: {request.data}")
            serializer = LoginSerializer(data=request.data)
            if serializer.is_valid():
                username = serializer.validated_data['username']
                password = serializer.validated_data['password']

                try:
                    # Check if the user exists
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    return Response({'error': 'User does not exist'}, status=400)

                # Authenticate the user
                user = authenticate(username=username, password=password)
                if user is None:
                    return Response({'error': 'Password is not valid'}, status=400)

                if user:
                    # Send email verification for login
                    send_mail_for_login(user)

                    refresh = RefreshToken.for_user(user)
                    access_token = refresh.access_token

                    login(request, user)

                    response_data = {
                        "message": "Login successful!",
                        "access_token": str(access_token),
                        "refresh_token": str(refresh),
                    }
                    response = Response(response_data, status=status.HTTP_200_OK)
                    response.set_cookie('status', 'true', httponly=True, max_age=timedelta(days=1))  # Expires in 1 day
                    response.set_cookie('username', user.username, httponly=True, max_age=timedelta(days=1))  # Expires in 1 day
                    logger.info(f"User {user.username} logged in successfully")
                    return response

                logger.error(f"Invalid credentials for user {username}")
                return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

            logger.error(f"Serializer errors: {serializer.errors}")
            return Response({"errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.exception(f"Error during login: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Register View
class RegisterView(APIView):
    @csrf_exempt
    def post(self, request):
        """Register a new user and send OTP verification email."""

        email = request.data.get('email')
        username = request.data.get('username')

        # Check if the username already exists
        if User.objects.filter(username=username).exists():
            logger.warning(f"Registration failed: Username {username} already exists.")
            return Response({"username": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)
     
        # Check if the email already exists
        if User.objects.filter(email=email).exists():
            logger.warning(f"Registration failed: Email {email} already exists.")
            return Response({"email": "Email address is already taken."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            send_mail_for_register(user)
            logger.info(f"User {user.username} registered successfully")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        logger.error(f"Registration failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
