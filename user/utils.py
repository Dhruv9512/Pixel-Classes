import os
import random
import logging
from datetime import timedelta
from hashlib import md5

# Django & Celery Imports
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from .models import PasswordResetToken

# Brevo API client imports
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Set up a logger for this module
logger = logging.getLogger(__name__)

# ==============================================================================
# BREVO API CLIENT CONFIGURATION
# This setup is done once when the Celery worker starts.
# ==============================================================================

# Ensure these environment variables are set: BREVO_API_KEY, BREVO_SENDER_EMAIL
DEFAULT_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL')
DEFAULT_SENDER_NAME = "PixelClasses" # You can customize the sender name here

# Configure the Brevo API client
configuration = sib_api_v3_sdk.Configuration()
brevo_api_key = os.getenv('BREVO_API_KEY')

if not brevo_api_key or not DEFAULT_SENDER_EMAIL:
    logger.critical("FATAL: BREVO_API_KEY or BREVO_SENDER_EMAIL environment variable not found. Email sending will fail.")
else:
    configuration.api_key['api-key'] = brevo_api_key
    logger.info("Brevo API client configured successfully.")

# Create a shared API instance
api_client = sib_api_v3_sdk.ApiClient(configuration)
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)

# ==============================================================================
# EMAIL SENDING HELPER
# This function uses the globally configured Brevo client.
# ==============================================================================

def _send_templated_email(*, subject: str, to_email: str, html_template: str, context: dict, plain_fallback: str):
    """
    A helper function to render and send a transactional email using the Brevo API.
    """
    if not configuration.api_key.get('api-key'):
        logger.error("Cannot send email because Brevo API key is not configured.")
        # Fail silently in production or raise an error in development
        raise ValueError("Brevo API key is missing.")

    # Render the HTML content from a Django template
    html_message = render_to_string(html_template, context or {})

    # Define the sender and recipient
    sender = {"name": DEFAULT_SENDER_NAME, "email": DEFAULT_SENDER_EMAIL}
    to = [{"email": to_email}]

    # Create the email object using the Brevo SDK
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject=subject,
        html_content=html_message,
        text_content=plain_fallback
    )

    # Send the email via the Brevo API
    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Email '{subject}' sent to {to_email} via Brevo. Message ID: {api_response.message_id}")
    except ApiException as e:
        logger.error(f"Brevo API error when sending email to {to_email}: {e.body}")
        # Re-raise the exception to allow Celery to handle retries
        raise e

# ==============================================================================
# UTILITY FUNCTIONS (No changes)
# ==============================================================================

def generate_otp():
    """Generate a random 6-digit OTP."""
    otp = f"{random.randint(100000, 999999)}"
    logger.debug(f"Generated OTP: {otp}")
    return otp

def generate_reset_token(user):
    """Generate and store a password reset token for a user."""
    PasswordResetToken.objects.filter(expiry_date__lt=timezone.now()).delete()
    PasswordResetToken.objects.filter(user=user).delete()
    token = default_token_generator.make_token(user)
    expiry_date = timezone.now() + timedelta(hours=1)
    PasswordResetToken.objects.create(user=user, token=token, expiry_date=expiry_date)
    return token

# ==============================================================================
# UPDATED CELERY TASKS
# These tasks now use the new _send_templated_email helper.
# ==============================================================================

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_mail_for_register(self, user_data=None):
    """Send OTP to user for registration."""
    if not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    otp = user_data.get("otp")
    if not username or not otp:
        raise ValueError("Username or OTP is missing in user_data")

    user = User.objects.only('email').filter(username=username).first()
    if not user:
        logger.error(f"User with username {username} does not exist for OTP email.")
        return

    _send_templated_email(
        subject='Email Verification',
        to_email=user.email,
        html_template='Signup/Email_Register_OTP.html',
        context={'username': username, 'otp': otp, 'current_year': timezone.now().year},
        plain_fallback=f"Hello {username}, your verification OTP is: {otp}"
    )
    logger.info(f"Queued OTP email for {user.email}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_mail_for_login(self, user_data=None):
    """Send login verification email to the user."""
    if not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    email = user_data.get("email")
    if not username or not email:
        raise ValueError("Username or email is missing in user_data")

    _send_templated_email(
        subject='Login Verification',
        to_email=email,
        html_template='Login/email_verification_For_Login.html',
        context={'username': username},
        plain_fallback=f"Hello {username},\n\nThere was a recent login to your account. If this was not you, please secure your account immediately."
    )
    logger.info(f"Queued login verification email for {email}")


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_password_reset_email(self, user_data=None):
    """Sends a password reset email to the user with a link."""
    if not isinstance(user_data, dict):
        raise ValueError(f"Expected user_data to be a dictionary, got {type(user_data)}")

    username = user_data.get("username")
    email = user_data.get("email")
    reset_url = user_data.get("reset_url")
    if not username or not email or not reset_url:
        raise ValueError("Username, email, or reset URL is missing in user_data")

    _send_templated_email(
        subject="Password Reset Request",
        to_email=email,
        html_template='reset_password/send_password_reset_email.html',
        context={'url': reset_url, 'username': username},
        plain_fallback=f"Hello {username},\n\nPlease use the following link to reset your password:\n{reset_url}"
    )
    logger.info(f"Queued password reset email for {email}")


# ==============================================================================
# CACHE KEY HELPERS (No changes)
# ==============================================================================

def user_cache_key(request, key_prefix, cache_key):
    """Generate a cache key based on the user."""
    user_id = request.user.pk if getattr(request.user, "is_authenticated", False) else "anon"
    raw = f"user_cache:v1:{user_id}"
    return md5(raw.encode("utf-8")).hexdigest()

def user_key(user):
    """Generate a cache key for a specific user object."""
    raw = f"user_cache:v1:{user.pk}"
    return md5(raw.encode("utf-8")).hexdigest()