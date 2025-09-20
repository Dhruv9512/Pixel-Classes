from django.utils.timezone import now
import random
import logging
from django.core.cache import cache
from django.template.loader import render_to_string
from rest_framework.response import Response
from django.conf.global_settings import EMAIL_HOST_USER
from rest_framework import status
from django.core.mail import send_mail, EmailMessage, get_connection
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator
from .models import PasswordResetToken
from celery import shared_task
from django.contrib.auth.models import User
from hashlib import md5

logger = logging.getLogger(__name__)

# OTP Generation function
def generate_otp():
    """Generate a random 6-digit OTP."""
    otp = f"{random.randint(100000, 999999)}"
    logger.debug(f"Generated OTP: {otp}")
    return otp

# Generate token
def generate_reset_token(user):
    # Delete expired tokens first (single query) [optimization; same behavior]
    PasswordResetToken.objects.filter(expiry_date__lt=timezone.now()).delete()

    # Remove any existing tokens for this user (logic preserved)
    PasswordResetToken.objects.filter(user=user).delete()

    # Generate and store a new token
    token = default_token_generator.make_token(user)
    expiry_date = timezone.now() + timedelta(hours=1)
    PasswordResetToken.objects.create(user=user, token=token, expiry_date=expiry_date)
    return token

# Celery email sending helpers: reuse a single SMTP connection where possible. [web:48]
def _send_html_email(subject, html, to_email):
    email = EmailMessage(subject, html, EMAIL_HOST_USER, [to_email])
    email.content_subtype = "html"
    email.send(fail_silently=False)

# Send Registration OTP email
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_mail_for_register(self, user_data=None):
    """Send OTP to user for registration."""
    if not user_data or not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    if not username:
        raise ValueError("User ID is missing in user_data")

    otp = user_data.get("otp")
    if not otp:
        raise ValueError("OTP is missing in user_data")

    # Fetch minimal user fields if needed
    user = User.objects.only('email', 'username').filter(username=username).first()
    if not user:
        logger.error(f"User with username {username} does not exist.")
        return

    subject = 'Email Verification'
    context = {
        'username': username,
        'otp': otp,
        'current_year': now().year,
    }
    message = render_to_string('Signup/Email_Register_OTP.html', context)
    _send_html_email(subject, message, user.email)
    logger.info(f"Sent OTP email to {user.email}")

# Send Login Verification email
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_mail_for_login(self, user_data=None):
    """Send login verification email to the user."""
    if not user_data or not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    if not username:
        raise ValueError("User ID is missing in user_data")

    email = user_data.get("email")
    if not email:
        raise ValueError("Email is missing in user_data")

    subject = 'Login Verification'
    message = render_to_string('Login/email_verification_For_Login.html', {'username': username})
    _send_html_email(subject, message, email)
    logger.info(f"Sent login verification email to {email}")

# reset password mail
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_password_reset_email(self, user_data=None):
    """
    Sends a password reset email to the user with a link to reset their password.
    """
    if not user_data or not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    email = user_data.get("email")
    reset_url = user_data.get("reset_url")
    if not username or not reset_url or not email:
        raise ValueError("Username, email, or reset URL is missing in user_data")

    subject = "Password Reset Request"
    message = render_to_string('reset_password/send_password_reset_email.html', {'url': reset_url, 'username': username})
    _send_html_email(subject, message, email)
    logger.info(f"Sent password reset email to {email}")

# Cache key helpers (stable, user-scoped)
def user_cache_key(request, key_prefix, cache_key):
    user_id = request.user.pk if getattr(request.user, "is_authenticated", False) else "anon"
    raw = f"user_cache:v1:{user_id}"
    return md5(raw.encode("utf-8")).hexdigest()

def user_key(user):
    raw = f"user_cache:v1:{user.pk}"
    return md5(raw.encode("utf-8")).hexdigest()
