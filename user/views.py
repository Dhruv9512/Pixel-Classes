from django.contrib.auth import authenticate, login
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseRedirect
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.management.utils import get_random_secret_key
import random
from datetime import timedelta
from django.core.cache import cache  
import logging

# Set up logging
logger = logging.getLogger(__name__)

# OTP Generation function
def generate_otp():
    """Generate a random 6-digit OTP."""
    otp = str(random.randint(100000, 999999))
    logger.debug(f"Generated OTP: {otp}")
    return otp

# Send Registration OTP email
def send_mail_for_register(user):
    """Send OTP to user for registration."""
    otp = generate_otp()

    # Store OTP in cache (expires in 5 minutes)
    cache.set(f"otp_{user.pk}", otp, timeout=300)
    logger.debug(f"OTP for user {user.username} stored in cache")

    subject = 'Email Verification'
    context = {
        'username': user.username,
        'otp': otp,
        'current_year': now().year,
    }

    try:
        message = render_to_string('Signup/Email_Register_OTP.html', context)
        send_mail(subject, message, EMAIL_HOST_USER, [user.email], html_message=message, fail_silently=False)
        logger.info(f"Sent OTP email to {user.email}")
        context1 = {
            'username': user.email,
            'otp': otp,
        }
        return Response(context1, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        raise

# Send Login Verification email
def send_mail_for_login(user):
    """Send login verification email to the user."""
    subject = 'Login Verification'
    message = render_to_string('Login/email_verification_For_Login.html', {
        'user': user,
    })
    try:
        send_mail(subject, message, EMAIL_HOST_USER, [user.email], html_message=message)
        logger.info(f"Sent login verification email to {user.email}")
    except Exception as e:
        logger.error(f"Error sending login verification email: {str(e)}")

# OTP Verification View
class VerifyOTPView(APIView):
    @csrf_exempt
    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"OTP verification failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        otp = serializer.validated_data['otp']
        email = request.data.get('email')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email address."}, status=status.HTTP_404_NOT_FOUND)

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

                user = authenticate(username=username, password=password)
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
