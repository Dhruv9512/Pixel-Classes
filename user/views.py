from django.contrib.auth import authenticate, login
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer, PasswordResetSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.tokens import default_token_generator
from .utils import send_mail_for_register, send_mail_for_login, send_password_reset_email,send_password_reset_confirmation,generate_reset_token
from datetime import timedelta
from django.core.cache import cache  
import logging
from datetime import timedelta
from django.shortcuts import HttpResponseRedirect
from .models import PasswordResetToken 
from django.utils.timezone import now
import schedule
from django.utils import timezone

def health_check():
    try:
        # Directly query for expired tokens instead of fetching all tokens
        expired_tokens = PasswordResetToken.objects.filter(expiry_date__lt=timezone.now())
    
        # Delete the expired tokens in bulk to reduce database hits
        expired_tokens.delete()
    except Exception as e:
        print(f"An error occurred: {e}")

schedule.every(1).hour.do(health_check)

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
            token = generate_reset_token(user)

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
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({"error": "No user found with this ID."}, status=status.HTTP_404_NOT_FOUND)

        if default_token_generator.check_token(user, token):
            try:
                password_reset_token = PasswordResetToken.objects.get(user=user, token=token)
                if password_reset_token.expiry_date < now():
                    return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

                password_reset_token.is_verified = True
                password_reset_token.save()

                # Redirect and set cookies
                redirect_url = f"https://pixelclass.netlify.app/newpassword/{token}"
                response = HttpResponseRedirect(redirect_url)

                return response
            except PasswordResetToken.DoesNotExist:
                return Response({"error": "No reset token found for this user."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

# SubmitNewPasswordView

class SubmitNewPasswordView(APIView):
    @csrf_exempt
    def post(self, request):
        # Validate input using the serializer
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            token_value = serializer.validated_data['token']
            new_password = serializer.validated_data['new_password']

            try:
                # Retrieve the token and validate it
                token = PasswordResetToken.objects.get(token=token_value, is_verified=True, is_reset=False)
                if token.is_expired():
                    return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

                # Retrieve the user associated with the token
                user = token.user

            except PasswordResetToken.DoesNotExist:
                return Response({"error": "Invalid or expired token."}, status=status.HTTP_404_NOT_FOUND)

            # Update the user's password
            user.set_password(new_password)
            user.save()

            # Mark the token as used
            token.is_reset = True
            token.save()

            # (Optional) Send a password reset confirmation email
            # send_password_reset_confirmation(user)

            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# PasswordResetStatusView
class PasswordResetStatusView(APIView):
    @csrf_exempt
    def post(self, request):
        # Get user_id from the POST data (assuming it's sent as part of the request body)
        email = request.data.get('email')  
        
        if not email:
            return Response({"error": "User ID not provided in the request."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch the user by user_id
        try:
            # Get the latest user by the email, ordering by 'created_at' in descending order
            user = User.objects.filter(email=email).order_by('-created_at').first()
        except User.DoesNotExist:
            return Response({"error": "No user found with this ID."}, status=status.HTTP_404_NOT_FOUND)

        # Assuming user has `is_verified` and `is_reset` flags. Modify according to your model.
        is_verified = getattr(user, 'is_verified', False)  # Defaults to False if not found
        is_reset = getattr(user, 'is_reset', False)  # Defaults to False if not found

        # Return the response with the user's password reset status
        return Response({
            "is_verified": is_verified,
            "is_reset": is_reset,
            "message": "Password reset status retrieved successfully."
        }, status=status.HTTP_200_OK)