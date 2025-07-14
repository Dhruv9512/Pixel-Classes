import email
from django.contrib.auth import authenticate, login
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer, PasswordResetSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from .utils import send_mail_for_register, send_mail_for_login, send_password_reset_email,generate_reset_token
from datetime import timedelta
from django.core.cache import cache  
import logging
from datetime import timedelta
from django.shortcuts import HttpResponseRedirect
from django.http import HttpResponse
import urllib
from .models import PasswordResetToken 
from django.utils.timezone import now
import time
from Profile.serializers import profileSerializer
import requests
from google.oauth2 import id_token  
import os
from google.auth.transport.requests import Request


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
        for _ in range(3):  # Retry fetching in case of a delay
            try:
                user = User.objects.get(username=username)
                break
            except User.DoesNotExist:
                time.sleep(0.5)  
        else:
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

            # Send email verification for login
            user_data = RegisterSerializer(user).data
            send_mail_for_login.apply_async(aargs = [user_data])

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
        else:
            logger.warning(f"Invalid OTP entered for user: {user.username}")
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)       

# Google Login Verification View
@method_decorator(csrf_exempt, name='dispatch')
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # ✅ Token Verification (IO-bound)
            idinfo = id_token.verify_oauth2_token(
                token,
                Request(),
                os.environ.get('GOOGLE_CLIENT_ID')
            )
            email = idinfo.get('email')
            if not email:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Fast user data fetch (dict only)
            user_data = User.objects.only('id', 'username', 'email').filter(email=email).values('id', 'username', 'email').first()
            if not user_data:
                return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_404_NOT_FOUND)

            # ✅ Rebuild user object (without DB hit)
            user = User(id=user_data['id'], username=user_data['username'], email=user_data['email'])

            # ✅ Login user (session)
            login(request, user)

            # ✅ JWT Token generation
            refresh = RefreshToken.for_user(user)

            # ✅ Fire async email (non-blocking)
            try:
                send_mail_for_login.delay(user_data)  
            except Exception as e:
                logger.warning(f"Email send failed for {user_data['username']}: {e}")

            logger.info(f"User {user_data['username']} logged in via Google.")

            # ✅ Return fast response
            return Response({
                "message": "Login successful!",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "username": user_data['username'],
            }, status=status.HTTP_200_OK)

        except ValueError:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Google login failed.")
            return Response({"error": "Something went wrong. Try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Google signup verification view
@method_decorator(csrf_exempt, name='dispatch')
class GoogleSignupAPIView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token,
                Request(),
                os.environ.get('GOOGLE_CLIENT_ID')
            )
            email = idinfo.get('email')
            username=idinfo.get('name', email.split('@')[0])
            if User.objects.filter(username=username).exists():
                username = email.split('@')[0].lower()
            first_name = idinfo.get('given_name', '')
            last_name = idinfo.get('family_name', '') 
            
            if not email:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if user already exists
            user, created = User.objects.get_or_create(email=email, defaults={'username': username, 'is_active': False, 'first_name': first_name, 'last_name': last_name})
            if not created:
                return Response({"error": "User already exists. Please login."}, status=status.HTTP_400_BAD_REQUEST)

            
            # Set user as active and save
            user.is_active = True
            user.save()

            # Send welcome email asynchronously
            try:
                user_data = RegisterSerializer(user).data
                send_mail_for_register.apply_async(args=[user_data])
            except Exception as e:
                logger.warning(f"Email send failed for {user.username}: {e}")
            # Login user
            login(request, user)

            # ✅ JWT Token generation
            refresh = RefreshToken.for_user(user)

            # ✅ Return fast response
            return Response({
                "message": "Signup successful!",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "username": user_data['username'],
            }, status=status.HTTP_200_OK)    
        except ValueError:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Google signup failed.")
            return Response({"error": "Something went wrong. Try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Login View
class LoginView(APIView):
    @csrf_exempt
    def post(self, request):
        """Authenticate and login user, send verification email."""
        try:
            logger.debug(f"Login attempt for data: {request.data}")
            serializer = LoginSerializer(data=request.data)

            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            username = serializer.validated_data['username']
            password = serializer.validated_data['password']

            # Check if the user exists
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_404_NOT_FOUND)

            # Authenticate credentials
            user_auth = authenticate(username=username, password=password)
            if not user_auth:
                return Response({"error": "Incorrect password. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

            # Check user is active
            if not user_auth.is_active:
                return Response({"error": "You are not verified yet. Please check your email or try later."}, status=status.HTTP_403_FORBIDDEN)

            # Send login email (won't affect flow if fails)
            try:
                user_data = RegisterSerializer(user).data
                send_mail_for_login.apply_async(args=[user_data])
            except Exception as email_err:
                logger.warning(f"Login email failed: {str(email_err)}")

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            # Login user
            login(request, user)

            # Prepare response
            response_data = {
                "message": "Login successful!",
                "access_token": str(access_token),
                "refresh_token": str(refresh),
                "username": user.username,
            }

            response = Response(response_data, status=status.HTTP_200_OK)
            logger.info(f"User '{user.username}' logged in successfully")
            return response

        except Exception as e:
            logger.exception(f"Error during login: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterView(APIView):
    @csrf_exempt
    def post(self, request):
        """Register a new user and send OTP verification email."""

        try:
            # Clean up non-verified inactive users
            User.objects.filter(is_active=False, last_login__isnull=True).delete()

            email = request.data.get('email')
            username = request.data.get('username')

            # Validate email and username uniqueness
            if User.objects.filter(email=email).exists():
                logger.warning(f"Registration failed: Email {email} already exists.")
                return Response({"error": "Email address is already taken."}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username=username).exists():
                logger.warning(f"Registration failed: Username {username} already exists.")
                return Response({"error": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)

            # Validate and save user
            serializer = RegisterSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"User serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            user = serializer.save()

            # Validate and save user profile
            profile_data = {**request.data, "user_obj": user.id}
            pf = profileSerializer(data=profile_data)
            if not pf.is_valid():
                user.delete()  # Rollback user if profile fails
                logger.error(f"Profile creation failed: {pf.errors}")
                return Response(pf.errors, status=status.HTTP_400_BAD_REQUEST)

            pf.save()

            # Send email asynchronously
            try:
                user_data = RegisterSerializer(user).data
                send_mail_for_register.apply_async(args=[user_data])
            except Exception as e:
                logger.warning(f"Email sending failed during registration: {str(e)}")

            # Prepare response with secure cookies
            response = Response(serializer.data, status=status.HTTP_201_CREATED)
            response.set_cookie('status', 'false', httponly=True, max_age=86400, secure=True, samesite='None')
            response.set_cookie('username', username, httponly=True, max_age=86400, secure=True, samesite='None')

            logger.info(f"User '{username}' registered successfully")
            return response

        except Exception as e:
            logger.exception(f"Unexpected error during registration: {str(e)}")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Resend OTP View
class ResendOTPView(APIView):
    """View to resend OTP to the user."""

    @csrf_exempt
    def post(self, request):
        username = request.data.get('username')

        # Validate input
        if not username:
            logger.warning("Resend OTP failed: Username not provided.")
            return Response({"error": "Username is required. Please retry login."}, status=status.HTTP_400_BAD_REQUEST)

        # Attempt to get the user
        user = User.objects.filter(username=username).first()
        if not user:
            logger.warning(f"Resend OTP failed: No user found with username '{username}'.")
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Send OTP email asynchronously
            try:
                user_data = RegisterSerializer(user).data
                send_mail_for_register.apply_async(args=[user_data])
                logger.info(f"Resent OTP email to {user.email}")
            except Exception as e:
                logger.warning(f"Error sending OTP email: {str(e)}")
            
            return Response({"message": "OTP resent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error resending OTP email to {user.email}: {str(e)}")
            return Response({"error": "Error resending OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetRequestView
class PasswordResetRequestView(APIView):
    @csrf_exempt
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Try to find user, but don't leak whether they exist
        user = User.objects.filter(email=email).first()
        if not user:
            logger.warning(f"Password reset attempted for non-existent email: {email}")
            return Response({"message": "If the email exists, a reset link has been sent."}, status=status.HTTP_200_OK)

        try:
            # Generate password reset token and URL
            token = generate_reset_token(user)
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', args=[user.pk, token])
            )

            # Prepare data and send email asynchronously
            try:
                data = RegisterSerializer(user).data
                data["reset_url"] = reset_url
                send_password_reset_email.apply_async(args=[data])
                logger.info(f"Password reset email sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")

            return Response({"message": "If the email exists, a reset link has been sent."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error during password reset for {email}: {str(e)}")
            return Response({"error": "An error occurred while processing your request."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetConfirmView
class PasswordResetConfirmView(APIView):
    @csrf_exempt
    def get(self, request, user_id, token):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(f"Password reset attempt for invalid user ID: {user_id}")
            return Response({"error": "No user found with this ID."}, status=status.HTTP_404_NOT_FOUND)

        # Check if token is valid
        if not default_token_generator.check_token(user, token):
            logger.warning(f"Invalid password reset token used for user {user.email}")
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            password_reset_token = PasswordResetToken.objects.get(user=user, token=token)
        except PasswordResetToken.DoesNotExist:
            logger.error(f"No matching PasswordResetToken found for user {user.email}")
            return Response({"error": "No reset token found for this user."}, status=status.HTTP_400_BAD_REQUEST)

        # Check expiry
        if password_reset_token.expiry_date < now():
            logger.info(f"Expired token used for password reset by {user.email}")
            return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark token as verified
        try:
            password_reset_token.is_verified = True
            password_reset_token.save()
        except Exception as e:
            logger.error(f"Failed to mark token verified for user {user.email}: {str(e)}")
            return Response({"error": "Could not verify token."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Redirect to frontend password reset page
        redirect_url = f"https://pixelclass.netlify.app/newpassword/{token}"
        logger.info(f"Redirecting {user.email} to reset password page")
        return HttpResponseRedirect(redirect_url)


# SubmitNewPasswordView
class SubmitNewPasswordView(APIView):
    @csrf_exempt
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_value = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            # Try to fetch token
            token = PasswordResetToken.objects.get(token=token_value, is_verified=True, is_reset=False)
        except PasswordResetToken.DoesNotExist:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_404_NOT_FOUND)

        if token.is_expired():
            return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

        user = token.user
        try:
            # Update password and save user
            user.set_password(new_password)
            user.save()

            # Mark the token as used
            token.is_reset = True
            token.save()

            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error while resetting password for {user.email}: {e}")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetStatusView
class PasswordResetStatusView(APIView):
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error": "Email not provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Get user and latest token
            user = User.objects.filter(email=email).first()
            if not user:
                return Response(
                    {"error": "No user found with this email."},
                    status=status.HTTP_404_NOT_FOUND
                )

            token = PasswordResetToken.objects.filter(user=user).order_by('-created_at').first()
            if not token:
                return Response(
                    {"error": "No password reset token found for this user."},
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "is_verified": token.is_verified,
                    "is_reset": token.is_reset,
                    "message": "Password reset status retrieved successfully."
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(f"Error retrieving password reset status for {email}")
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# sanding cute email to nusarat
from django.core.mail import send_mail
from django.template.loader import render_to_string
class SendCuteEmail(APIView):
    def get(self, request):
        try:
            # Email details
            subject = "Welcome to Pixel, with Love"
            recipient_email = ["mitsuhamitsuha123@gmail.com"]
            message = render_to_string('Signup/mitsuha.html')
            
            # ✅ Try sending email
            try:
               
                send_mail(
                    subject, 
                    "",  
                    EMAIL_HOST_USER, 
                    [recipient_email[0]],  
                    html_message=message  
                )
            except Exception as e:
                print("❌ Email Sending Error:", str(e))
                return Response({"error": f"Email sending failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ✅ Encode subject for URL safety
            encoded_subject = urllib.parse.quote(subject)

            # ✅ Gmail intent URL
            gmail_web_url = f"https://mail.google.com/mail/#inbox"

            html_response = f"""
            <html>
                <body>
                    <script>
                        window.location.href = "{gmail_web_url}";
                    </script>
                    <p>If you are not redirected, <a href="{gmail_web_url}">click here</a>.</p>
                </body>
            </html>
            """
            
            return HttpResponse(html_response)

        except Exception as e:
            print("❌ API Error:", str(e))
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
