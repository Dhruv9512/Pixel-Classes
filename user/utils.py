from django.utils.timezone import now
import random
import logging
from django.core.cache import cache 
from django.template.loader import render_to_string
from rest_framework.response import Response
from django.conf.global_settings import EMAIL_HOST_USER
from rest_framework import status
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from .models import PasswordResetToken
from django.core.mail import send_mail
from celery import shared_task
from django.contrib.auth.models import User 



# Set up logging
logger = logging.getLogger(__name__)

# OTP Generation function
def generate_otp():
    """Generate a random 6-digit OTP."""
    otp = str(random.randint(100000, 999999))
    logger.debug(f"Generated OTP: {otp}")
    return otp

# Generate token
def generate_reset_token(user):
    # Delete expired tokens
    expired_tokens = PasswordResetToken.objects.filter(expiry_date__lt=timezone.now())
    expired_tokens.delete()

    # Delete any existing valid token for the user before generating a new one
    PasswordResetToken.objects.filter(user=user).delete()

    # Generate a new token
    token = default_token_generator.make_token(user)

    # Set token expiration date (1 hour from now)
    expiry_date = timezone.now() + timedelta(hours=1)

    # Save the new token in the database
    password_reset_token = PasswordResetToken(
        user=user,
        token=token,
        expiry_date=expiry_date
    )
    password_reset_token.save()

    return token  # Return the newly generated token


    return token
# Send Registration OTP email
@shared_task(name="user.utils.send_mail_for_register")
def send_mail_for_register(user_data=None):
    """Send OTP to user for registration."""
    try:
        if not user_data or not isinstance(user_data, dict):
            raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

        user_id = user_data.get("id")
        if not user_id:
            raise ValueError("User ID is missing in user_data")

        user = User.objects.get(id=user_id)  # Fetch user by ID
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

        message = render_to_string('Signup/Email_Register_OTP.html', context)
        send_mail(subject, message, EMAIL_HOST_USER, [user.email], html_message=message, fail_silently=False)
        logger.info(f"Sent OTP email to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with ID {user_data.get('id')} does not exist.")
    except Exception as e:
        logger.error(f"Error sending registration email: {str(e)}")


# Send Login Verification email
@shared_task(name="user.utils.send_mail_for_login")
def send_mail_for_login(user_data=None):
    """Send login verification email to the user."""
    try:
        if not user_data or not isinstance(user_data, dict):
            raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

        user_id = user_data.get("id")
        if not user_id:
            raise ValueError("User ID is missing in user_data")

        user = User.objects.get(id=user_id)  # Fetch user by ID
        subject = 'Login Verification'
        message = render_to_string('Login/email_verification_For_Login.html', {
            'user': user,
        })
        send_mail(subject, message, EMAIL_HOST_USER, [user.email], html_message=message)
        logger.info(f"Sent login verification email to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with ID {user_data.get('id')} does not exist.")
    except Exception as e:
        logger.error(f"Error sending login verification email: {str(e)}")


# reset password mail
@shared_task(name="user.utils.send_password_reset_email")
def send_password_reset_email(user_data=None):
    """
    Sends a password reset email to the user with a link to reset their password.
    """
    try:
        if not user_data or not isinstance(user_data, dict):
            raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

        user_id = user_data.get("id")
        reset_url = user_data.get("reset_url")
        if not user_id or not reset_url:
            raise ValueError("User ID or reset URL is missing in user_data")

        user = User.objects.get(id=user_id)  # Fetch user by ID
        subject = "Password Reset Request"
        message = render_to_string(
            'reset_password/send_password_reset_email.html',
            {'url': reset_url, 'username': user.username}
        )

        send_mail(
            subject,
            message,
            EMAIL_HOST_USER,  # Email address from settings
            [user.email],  # Recipient email address
            html_message=message  # HTML message version
        )
        logger.info(f"Sent password reset email to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User with ID {user_data.get('id')} does not exist.")
    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {str(e)}")
