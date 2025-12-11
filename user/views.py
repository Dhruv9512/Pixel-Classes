from urllib import response
from django.contrib.auth import authenticate, login
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .serializers import LoginSerializer, RegisterSerializer, OTPSerializer, PasswordResetSerializer, ManualRegisterSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.urls import reverse
from django.conf.global_settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from .utils import generate_otp, send_mail_for_register, send_mail_for_login, send_password_reset_email, generate_reset_token, user_key
from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
import logging
from datetime import timedelta
from django.shortcuts import HttpResponseRedirect
from django.http import HttpResponse
import urllib
from .models import PasswordResetToken
from django.utils.timezone import now
import time
from google.oauth2 import id_token
import os
from google.auth.transport import requests as g_requests
from vercel_blob import put
from django.views.decorators.cache import never_cache
from .authentication import CookieJWTAuthentication
from django.conf import settings

# Optimizations
# - Use minimal column selection with only()/values()/first() per Django guidance. [web:27]
# - Cache Google cert fetch for verify_oauth2_token using cachecontrol-backed session. [web:7][web:26]
# - Centralize cookie setting with SameSite=None + Secure + HttpOnly (per modern browser rules). [web:6]

import requests as _req
import cachecontrol

_cached_session = cachecontrol.CacheControl(_req.session())  # cache Google certs [web:7]
_google_request = g_requests.Request(session=_cached_session)  # pass to id_token.verify_oauth2_token [web:26]

# Set up logging
logger = logging.getLogger(__name__)

# Helper to set auth cookies consistently with proper attributes. [web:6]
def _set_auth_cookies(response, access_token, refresh_token):
    response.set_cookie(
        key="access",
        value=str(access_token),
        httponly=True,
        secure=True,
        samesite="None",
        max_age=30 * 60,
    )
    response.set_cookie(
        key="refresh",
        value=str(refresh_token),
        httponly=True,
        secure=True,
        samesite="None",
        max_age=7 * 24 * 60 * 60,
    )
    return response


# OTP Verification View
@method_decorator(never_cache, name="dispatch")
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt  # Exempt CSRF for this endpoint
    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"OTP verification failed: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        otp = serializer.validated_data['otp']
        username = request.data.get('username')

        if not username:
            return Response({"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Poll with filter().first() to avoid exception-based control flow; only needed fields. [web:27]
        user = None
        for _ in range(4):
            user = User.objects.only('id', 'username', 'is_active').filter(username=username).first()
            if user:
                break
            time.sleep(0.5)
        if not user:
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        stored_otp = cache.get(f"otp_{user.pk}")
        if not stored_otp:
            return Response({"error": "OTP expired or not generated."}, status=400)

        if str(otp) == str(stored_otp):
            user.is_active = True
            user.save(update_fields=["is_active"])  # targeted update [web:27]
            cache.delete(f"otp_{user.pk}")
            logger.info(f"Account activated successfully for user: {user.username}")

            user_data = RegisterSerializer(user).data
            try:
                send_mail_for_login.apply_async(args=[user_data])
            except Exception as e:
                logger.warning(f"Login email enqueue failed for {user.username}: {e}")

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            login(request, user)

            response_data = {
                "message": "Login successful!",
                "status": "true",
            }
            response = Response(response_data, status=status.HTTP_200_OK)
            return _set_auth_cookies(response, access_token, refresh)
        else:
            logger.warning(f"Invalid OTP entered for user: {user.username}")
            return Response({"error": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)


# Google Login Verification View
@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class GoogleLoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use cached request to avoid repeated cert downloads. [web:7]
            idinfo = id_token.verify_oauth2_token(
                token,
                _google_request,
                os.environ.get('GOOGLE_CLIENT_ID')
            )
            email = idinfo.get('email')
            if email in ["forlaptop2626@gmail.com","mitsuhamitsuha123@gmail.com"]:
                return Response({"error": "User not eligible"}, status=status.HTTP_404_NOT_FOUND)
            if not email:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch minimal columns; avoid full model instantiation DB hit. [web:27]
            user_data = User.objects.only('id', 'username', 'email').filter(email=email).values('id', 'username', 'email').first()
            if not user_data:
                return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_404_NOT_FOUND)

            # Rebuild user instance without extra query (id, username, email). [web:27]
            user = User(id=user_data['id'], username=user_data['username'], email=user_data['email'])

            login(request, user)

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            try:
                send_mail_for_login.delay(user_data)
            except Exception as e:
                logger.warning(f"Email send failed for {user_data['username']}: {e}")

            logger.info(f"User {user_data['username']} logged in via Google.")

            response = Response({
                "message": "Login successful!",
                "satus": "true",
            }, status=status.HTTP_200_OK)

            return _set_auth_cookies(response, access_token, refresh)

        except ValueError:
            return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Google login failed.")
            return Response({"error": "Something went wrong. Try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Google signup verification view
import os
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.contrib.auth import login
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
import logging

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize the Google Request object (cached)
_google_request = google_requests.Request()

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(never_cache, name='dispatch')
class GoogleSignupAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token not provided'}, status=status.HTTP_400_BAD_REQUEST)

        # Define all valid Client IDs from your Expo config
        ALLOWED_CLIENT_IDS = [
            os.environ.get('GOOGLE_WEB_CLIENT_ID'),
            os.environ.get('GOOGLE_IOS_CLIENT_ID'),
            os.environ.get('GOOGLE_ANDROID_CLIENT_ID'),
        ]

        try:
            # 1. Verify the token signature, but skip the automatic audience check for now (audience=None)
            idinfo = id_token.verify_oauth2_token(
                token,
                _google_request, 
                audience=None 
            )

            # 2. Manually check if the token's audience matches one of your apps
            if idinfo['aud'] not in ALLOWED_CLIENT_IDS:
                raise ValueError('Could not verify audience.')

            # --- Existing Logic Starts Here ---
            email = idinfo.get('email')
            if email in ["forlaptop2626@gmail.com", "mitsuhamitsuha123@gmail.com"]:
                return Response({"error": "User not eligible"}, status=status.HTTP_404_NOT_FOUND)
            
            if not email:
                return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if user exists
            if User.objects.filter(email=email).only('id').exists():
                return Response({"error": "User already exists. Please log in."}, status=status.HTTP_400_BAD_REQUEST)

            base_username = idinfo.get('name', email.split('@')[0]).replace(" ", "_")
            username = base_username
            counter = 1
            while User.objects.filter(username=username).only('id').exists():
                username = f"{base_username}_{counter}"
                counter += 1

            serializer = RegisterSerializer(data={
                'username': username,
                'email': email,
                'first_name': idinfo.get('given_name', ''),
                'last_name': idinfo.get('family_name', ''),
                'is_active': True,
                'profile_pic': idinfo.get('picture', '')
            })

            if serializer.is_valid():
                user = serializer.save()
            else:
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            try:
                send_mail_for_login.apply_async(args=[serializer.data])
            except Exception as e:
                logger.warning(f"Email send failed for {user.username}: {e}")

            login(request, user)
            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            response = Response({
                "message": "Signup successful!",
                "status": "true",
            }, status=status.HTTP_200_OK)

            return _set_auth_cookies(response, access_token, refresh)

        except ValueError as e:
            # Helpful for debugging: print the specific error if needed
            logger.error(f"Token verification failed: {e}") 
            return Response({"error": "Invalid token or audience mismatch"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Google signup failed.")
            return Response({"error": "Something went wrong. Try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Login View
@method_decorator(never_cache, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]

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

            # Single hit with only() then authenticate. [web:27]
            user = User.objects.only('id', 'username', 'email', 'is_active').filter(username=username).first()
            if not user:
                return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_404_NOT_FOUND)
            if user.email in ["forlaptop2626@gmail.com","mitsuhamitsuha123@gmail.com"]:
                return Response({"error": "User not eligible"}, status=status.HTTP_404_NOT_FOUND)
            user_auth = authenticate(username=username, password=password)
            if not user_auth:
                return Response({"error": "Incorrect password. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

            if not user_auth.is_active:
                return Response({"error": "You are not verified yet. Please check your email or try later."}, status=status.HTTP_403_FORBIDDEN)

            try:
                user_data = RegisterSerializer(user).data
                send_mail_for_login.apply_async(args=[user_data])
            except Exception as email_err:
                logger.warning(f"Login email failed: {str(email_err)}")

            refresh = RefreshToken.for_user(user)
            access_token = refresh.access_token

            login(request, user)

            response_data = {
                "message": "Login successful!",
                "status": "true",
            }

            response = Response(response_data, status=status.HTTP_200_OK)
            return _set_auth_cookies(response, access_token, refresh)

        except Exception as e:
            logger.exception(f"Error during login: {str(e)}")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(never_cache, name="dispatch")
class RegisterView(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        """Register a new user and send OTP verification email."""
        try:
            # Clean up non-verified inactive users (unchanged).
            User.objects.filter(is_active=False, last_login__isnull=True).delete()

            email = request.data.get('email')
            username = request.data.get('username')
            profile_pic = request.data.get('profile_pic', "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
            course = request.data.get('course', "B.C.A")
            password = request.data.get('password')
            
            if profile_pic != "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp":
                blob = put(
                    f"Profile/{getattr(profile_pic, 'name', 'profile')}",
                    profile_pic.read(),
                    {"allowOverwrite": True}
                )
                profile_pic = blob["url"]
            if email in ["forlaptop2626@gmail.com","mitsuhamitsuha123@gmail.com"]:
                return Response({"error": "User not eligible"}, status=status.HTTP_404_NOT_FOUND)
            # Validate uniqueness with exists() + only('id') to minimize IO. [web:27]
            if User.objects.filter(email=email).only('id').exists():
                logger.warning(f"Registration failed: Email {email} already exists.")
                return Response({"error": "Email address is already taken."}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username__iexact=username).only('id').exists():
                return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

            data = {
                "username": username,
                "email": email,
                "password": password,
                "profile_pic": profile_pic,
                "course": course,
            }
            serializer = ManualRegisterSerializer(data=data)
            if not serializer.is_valid():
                logger.error(f"User serializer validation failed: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            user = serializer.save()

            otp = generate_otp()
            cache.set(f"otp_{user.pk}", otp, timeout=300)
            try:
                user_data = serializer.data
                user_data["otp"] = otp
                send_mail_for_register.apply_async(args=[user_data])
            except Exception as e:
                logger.warning(f"Email sending failed during registration: {str(e)}")

            response = Response(serializer.data, status=status.HTTP_201_CREATED)
            logger.info(f"User '{username}' registered successfully")
            return response

        except Exception as e:
            logger.exception(f"Unexpected error during registration: {str(e)}")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Resend OTP View
@method_decorator(never_cache, name="dispatch")
class ResendOTPView(APIView):
    """View to resend OTP to the user."""
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        username = request.data.get('username')

        if not username:
            logger.warning("Resend OTP failed: Username not provided.")
            return Response({"error": "Username is required. Please retry login."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.only('id', 'email', 'username').filter(username=username).first()
        if not user:
            logger.warning(f"Resend OTP failed: No user found with username '{username}'.")
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Regenerate OTP and set in cache (unchanged logic). [web:27]
            otp = generate_otp()
            cache.set(f"otp_{user.pk}", otp, timeout=300)
            try:
                user_data = RegisterSerializer(user).data
                user_data["otp"] = otp
                send_mail_for_register.apply_async(args=[user_data])
                logger.info(f"Resent OTP email to {user.email}")
            except Exception as e:
                logger.warning(f"Error sending OTP email: {str(e)}")

            return Response({"message": "OTP resent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception(f"Error resending OTP email to {user.email}: {str(e)}")
            return Response({"error": "Error resending OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetRequestView
@method_decorator(never_cache, name="dispatch")
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Use only() to minimize fields selected. [web:27]
        user = User.objects.only('id', 'email', 'username', 'first_name', 'last_name').filter(email=email).first()
        if not user:
            logger.warning(f"Password reset attempted for non-existent email: {email}")
            return Response({"message": "If the email exists, a reset link has been sent."}, status=status.HTTP_200_OK)

        try:
            token = generate_reset_token(user)
            reset_url = request.build_absolute_uri(
                reverse('password_reset_confirm', args=[user.pk, token])
            )

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
@method_decorator(never_cache, name="dispatch")
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt
    def get(self, request, user_id, token):
        try:
            user = User.objects.only('id', 'email').get(pk=user_id)
        except User.DoesNotExist:
            logger.warning(f"Password reset attempt for invalid user ID: {user_id}")
            return Response({"error": "No user found with this ID."}, status=status.HTTP_404_NOT_FOUND)

        if not default_token_generator.check_token(user, token):
            logger.warning(f"Invalid password reset token used for user {user.email}")
            return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            password_reset_token = PasswordResetToken.objects.only('id', 'expiry_date', 'is_verified').get(user=user, token=token)
        except PasswordResetToken.DoesNotExist:
            logger.error(f"No matching PasswordResetToken found for user {user.email}")
            return Response({"error": "No reset token found for this user."}, status=status.HTTP_400_BAD_REQUEST)

        if password_reset_token.expiry_date < now():
            logger.info(f"Expired token used for password reset by {user.email}")
            return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            password_reset_token.is_verified = True
            password_reset_token.save(update_fields=["is_verified"])
        except Exception as e:
            logger.error(f"Failed to mark token verified for user {user.email}: {str(e)}")
            return Response({"error": "Could not verify token."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        redirect_url = f"https://pixelclass.netlify.app/auth/password/{token}"
        logger.info(f"Redirecting {user.email} to reset password page")
        return HttpResponseRedirect(redirect_url)


# SubmitNewPasswordView
@method_decorator(never_cache, name="dispatch")
class SubmitNewPasswordView(APIView):
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_value = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']

        try:
            token = PasswordResetToken.objects.only('id', 'user_id').get(token=token_value, is_verified=True, is_reset=False)
        except PasswordResetToken.DoesNotExist:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_404_NOT_FOUND)

        if token.is_expired():
            return Response({"error": "Token has expired."}, status=status.HTTP_400_BAD_REQUEST)

        user = token.user
        try:
            user.set_password(new_password)
            user.save(update_fields=["password"])

            token.is_reset = True
            token.save(update_fields=["is_reset"])

            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error while resetting password for {getattr(user, 'email', 'unknown')}: {e}")
            return Response({"error": "Something went wrong. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PasswordResetStatusView
@method_decorator(never_cache, name="dispatch")
class PasswordResetStatusView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response(
                {"error": "Email not provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.only('id').filter(email=email).first()
            if not user:
                return Response(
                    {"error": "No user found with this email."},
                    status=status.HTTP_404_NOT_FOUND
                )

            token = PasswordResetToken.objects.filter(user=user).only('is_verified', 'is_reset', 'created_at').order_by('-created_at').first()
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


# Logout View
@method_decorator(never_cache, name="dispatch")
class LogoutView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.COOKIES.get('refresh')
        if not refresh_token:
            return Response({"error": "Refresh token missing"}, status=status.HTTP_401_UNAUTHORIZED)

        # Blacklist the refresh token
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as e:
            logger.warning(f"Invalid refresh token during logout: {str(e)}")
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            response = Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
            # Match attributes for deletion as set earlier if needed; Django delete_cookie handles basics. [web:6]
            response.delete_cookie('access')
            response.delete_cookie('refresh')
            try:
                cache.delete(user_key(user=request.user))
            except Exception:
                pass
            return response
        except Exception as e:
            logger.exception("Error during logout.")
            return Response({"error": "Internal server error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# sanding cute email to nusarat
from django.core.mail import send_mail
from django.template.loader import render_to_string


@method_decorator(never_cache, name="dispatch")
class SendCuteEmail(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        try:
            subject = "Sorry Nushu ❤️"
            recipient_email = ["mitsuhamitsuha123@gmail.com"]
            message = render_to_string('Signup/mitsuha.html')

            try:
                send_mail(
                    subject,
                    "",
                    EMAIL_HOST_USER,
                    [recipient_email[0]],
                    html_message=message
                )
            except Exception as e:
                return Response({"error": f"Email sending failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            return Response({"error": f"Internal Server Error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
