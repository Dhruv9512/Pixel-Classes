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
from .utils import send_mail_for_register, send_mail_for_login, send_password_reset_email,generate_reset_token,generate_otp
from datetime import timedelta
import traceback
from django.core.cache import cache  
import logging
from datetime import timedelta
from django.shortcuts import HttpResponseRedirect
from django.http import HttpResponse
import urllib
from .models import PasswordResetToken , OTP
from django.utils.timezone import now
from django.utils import timezone
import time
from Profile.serializers import profileSerializer
import requests

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
        username = request.data.get('username') 
        
        # Ensure username is provided in the request
        if not username:
            return Response({"error": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Fetch user from the database by username
        for _ in range(3):  
            try:
                user = User.objects.get(username=username)
                break
            except User.DoesNotExist:
                time.sleep(0.5)  
        else:
            return Response({"error": "No user found with this username."}, status=status.HTTP_404_NOT_FOUND)

        stored_otp = OTP.objects.filter(
            user=user, 
            created_at__gte=timezone.now() - timedelta(minutes=5)  # Ensure OTP is not expired
        ).order_by('-created_at').first()

        # Check if OTP is available or expired
        if stored_otp is None:
            logger.warning(f"OTP expired or not found in cache for user {username} with key otp_{user.pk}")
            return Response(
                {"error": "The OTP has expired or was not generated. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Compare the entered OTP with the stored OTP
        if otp == stored_otp:
            user.is_active = True  # Activate user account
            user.save()
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
                
            # Check if the username exists
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return Response({"error": "User does not exist. Please sign up first."}, status=status.HTTP_404_NOT_FOUND)

            # Check if the password is correct
            user_auth = authenticate(username=username, password=password)
            if user_auth is None:
                return Response({"error": "Incorrect password. Please try again."}, status=status.HTTP_401_UNAUTHORIZED)

            # Check if the user is inactive
            if not user_auth.is_active:
                return Response({"error": "You are not verified, please try to sign up tomorrow or wait for our email."}, status=status.HTTP_403_FORBIDDEN)
         
            # Send email verification for login
            user_data = RegisterSerializer(user).data
            send_mail_for_login.apply_async(args=[user_data]) 

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
        except Exception as e:
            logger.exception(f"Error during login: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RegisterView(APIView):
    @csrf_exempt
    def post(self, request):
        """Register a new user and send OTP verification email."""

        # Step 1: Delete non-verified users
        users = User.objects.filter(is_active=False, last_login__isnull=True)
        users.delete()

        email = request.data.get('email')
        username = request.data.get('username')

        # Step 2: Check if email or username already exists
        if User.objects.filter(email=email).exists():
            logger.warning(f"Registration failed: Email {email} already exists.")
            return Response({"error": "Email address is already taken."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            logger.warning(f"Registration failed: Username {username} already exists.")
            return Response({"error": "Username is already taken."}, status=status.HTTP_400_BAD_REQUEST)

        # Step 3: Validate user registration data
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            try:
                # Step 4: Create user profile
                pf = profileSerializer(data={**request.data, "user_obj": user.id}) 
                if pf.is_valid():
                    pf.save()
                else:
                    user.delete()  # Delete user if profile creation fails
                    logger.error(f"Profile creation failed: {pf.errors}")
                    return Response(pf.errors, status=status.HTTP_400_BAD_REQUEST)

                # Step 5: Set cookies
                response = Response(serializer.data, status=status.HTTP_201_CREATED)
                response.set_cookie('status', 'false', httponly=True, max_age=timedelta(days=1), secure=True, samesite='None')
                response.set_cookie('username', username, httponly=True, max_age=timedelta(days=1), secure=True, samesite='None')

                logger.info(f"User {username} registered successfully")

                # Step 6: Delete expired OTPs
                OTP.objects.filter(user=user, created_at__lt=timezone.now() - timedelta(minutes=5)).delete()

                # Step 7: Delete existing OTPs for the same user
                OTP.objects.filter(user=user).delete()

                # Step 8: Generate and store a new OTP
                otp = generate_otp()
                new_otp = OTP.objects.create(user=user, otp=otp)

                logger.info(f"OTP generated for {user.email}: {new_otp.otp}")

                # Step 9: Send email verification
                user_data = RegisterSerializer(user).data
                user_data["otp"] = otp
                send_mail_for_register.apply_async(args=[user_data])  # Celery Task

                return response

            except Exception as e:
                logger.error(f"Unexpected error during registration: {e}")
                traceback.print_exc()  # Print full error details in console
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
            # Delete any expired OTPs before generating a new one
            OTP.objects.filter(user=user, created_at__lt=timezone.now() - timedelta(minutes=5)).delete()

            # Delete any existing OTP for the same user (to ensure only one active OTP per user)
            OTP.objects.filter(user=user).delete()

            # Generate and store a new OTP
            otp = generate_otp()
            OTP.objects.create(user=user, otp=otp)

            # Send email verification for login
            user_data = RegisterSerializer(user).data
            user_data["otp"] = otp
            send_mail_for_register.apply_async(args=[user_data]) 
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
            data = RegisterSerializer(user).data
            data["reset_url"]= reset_url
                
            send_password_reset_email.apply_async(args=[data]) 
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

            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# PasswordResetStatusView
class PasswordResetStatusView(APIView):
    def post(self, request):
        try:
            # Extract email from the request body
            email = request.data.get('email')
            
            if not email:
                return Response(
                    {"error": "Email not provided in the request."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch the user by email
            user = User.objects.filter(email=email).first()

            if not user:
                return Response(
                    {"error": "No user found with this email."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Fetch the latest password reset token for the user
            token = PasswordResetToken.objects.filter(user=user).order_by('-created_at').first()

            if not token:
                return Response(
                    {"error": "No password reset token found for this user."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Retrieve password reset status flags
            is_verified = getattr(token, 'is_verified', False)
            is_reset = getattr(token, 'is_reset', False)

            # Return the password reset status
            return Response(
                {
                    "is_verified": is_verified,
                    "is_reset": is_reset,
                    "message": "Password reset status retrieved successfully."
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            import traceback
            print(traceback.format_exc())  
            return Response(
                {"error": f"An unexpected error occurred: {str(e)}"},
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
            recipient_email = ["dhruvsharma56780@gmail.com","mitsuhamitsuha123@gmail.com"]
            message = render_to_string('Signup/mitsuha.html')
            
            # ✅ Try sending email
            try:
                send_mail(
                    subject, 
                    "",  
                    EMAIL_HOST_USER, 
                    [recipient_email[1]],  
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
