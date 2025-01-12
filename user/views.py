from django.contrib.auth import authenticate, login
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer, PasswordResetSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.mail import send_mail
from django.urls import reverse
from django.template.loader import render_to_string
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.management.utils import get_random_secret_key
from .utils import send_mail_for_register, send_mail_for_login, generate_otp,send_password_reset_email,send_password_reset_confirmation
from datetime import timedelta
from django.core.cache import cache  
import logging
from datetime import timedelta
from django.shortcuts import redirect

# Set up logging
logger = logging.getLogger(__name__)

# OTP Verification View

class VerifyOTPView(APIView):
    @csrf_exempt  # Exempt CSRF for this endpoint
    def post(self, request):
        # Deserialize incoming OTP data
        serializer = OTPSerializer(data=request.data)
        
        # Validate OTP
        if not serializer.is_valid():
            logger.error(f"OTP verification failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        otp = serializer.validated_data['otp']
        username = request.data.get('username')  # Get username from request
        
        # Ensure username is provided in the request
        if not username:
            return Response({"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch user from the database by username
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve the stored OTP from cache
        stored_otp = cache.get(f"otp_{user.pk}")

        # Check if OTP is available or expired
        if stored_otp is None:
            return Response({"error": "OTP expired or not generated."}, status=status.HTTP_400_BAD_REQUEST)

        # Compare the entered OTP with the stored OTP
        if otp == stored_otp:
            user.is_active = True  # Activate user account
            user.save()
            cache.delete(f"otp_{user.pk}")  # Remove OTP from cache after verification
            logger.info(f"Account activated successfully for user: {user.username}")
            return Response({"message": "Account activated successfully."}, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Invalid OTP entered for user: {user.username}")
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
                
                # First, check if the user exists by verifying the username
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

                # Verify the password
                if not authenticate(username=username, password=password):
                    return Response({"error": "Invalid Password"}, status=status.HTTP_401_UNAUTHORIZED)

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
            logger.error(f"Serializer error: {serializer.errors}")
            return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.exception(f"Error during login: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegisterView(APIView):
    @csrf_exempt
    def post(self, request):
        """Register a new user and send OTP verification email."""
        email = request.data.get('email')
        username = request.data.get('username')

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            logger.warning(f"Registration failed: Email {email} already exists.")
            return Response({"error": "Email address is already taken."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            logger.warning(f"Registration failed: Username {username} already exists.")
            return Response({"error": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            response = Response(serializer.data, status=status.HTTP_201_CREATED)
            response.set_cookie('status', 'false', httponly=True, max_age=timedelta(days=1),secure=True, samesite='None')
            response.set_cookie('username', username, httponly=True, max_age=timedelta(days=1),secure=True, samesite='None')
            logger.info(f"User {username} registered successfully")
            send_mail_for_register(user)
            return response

        logger.error(f"Registration failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Resend OTP View
class ResendOTPView(APIView):
    """View to resend OTP to the user."""
    @csrf_exempt
    def post(self, request):
        username = request.data.get('username')
        
        # Ensure username is provided in the request
        if not username:
            return Response({"error": "Usename name error please retry to login again"}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch user from the database
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        try:
            send_mail_for_register(user)
            logger.info(f"Resent OTP email to {user.email}")
            return Response({"message": "OTP resent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error resending OTP email to {user.email}: {str(e)}")
            return Response({"error": "Error resending OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# PasswordResetRequestView
class PasswordResetRequestView(APIView):
    @csrf_exempt
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Find the user by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Generate a token using Django's default token generator
            token = default_token_generator.make_token(user)

            # Build the password reset URL, including the user ID and token
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', args=[user.pk, token])
            )

            # Send the reset link to the user's email
            send_password_reset_email(user,reset_url)
            logger.info(f"Password reset email sent to {user.email}")

            # Return a success response (Note: don't mention whether the user exists for security reasons)
            return Response({"message": "Password reset email has been sent."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            logger.warning(f"Password reset attempted for non-existent email: {email}")
            return Response({"message": "Password reset email has been sent."}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error during password reset process for {email}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetConfirmView

class PasswordResetConfirmView(APIView):
    @csrf_exempt
    def get(self, request, user_id, token):
        # Find the user by ID
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "No user found with this ID."}, status=status.HTTP_404_NOT_FOUND)

        # Check if the token is valid
        if default_token_generator.check_token(user, token):
            # Return a response indicating that the user is now able to reset their password
            redirect_url = "https://pixelclass.netlify.app/newpassword"

            # Redirect to the URL with the user ID
            response = redirect(redirect_url)
            response.set_cookie('user_id', user_id, httponly=True, secure=True, samesite='None')
            return response
        else:
            # If the token is invalid, return an error response
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
# SubmitNewPasswordView

class SubmitNewPasswordView(APIView):
    @csrf_exempt
    def post(self, request):
        # Validate input using the serializer
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            new_password = serializer.validated_data['new_password']

            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

            # Check if the password meets the necessary requirements
            if len(new_password) < 6:
                return Response({"error": "Password must be at least 6 characters long."}, status=status.HTTP_400_BAD_REQUEST)

            # Update the user's password
            user.set_password(new_password)
            user.save()

            # Send a password reset confirmation email (you can customize this function)
            send_password_reset_confirmation(user)

            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)