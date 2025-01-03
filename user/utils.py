
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

# Set up logging
logger = logging.getLogger(__name__)

# OTP Generation function
def generate_otp():
    """Generate a random 6-digit OTP."""
    otp = str(random.randint(100000, 999999))
    logger.debug(f"Generated OTP: {otp}")
    return otp

# Send Registration OTP email
@csrf_exempt
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
    except Exception as e:
        logger.error(f"Error sending email to {user.email}: {str(e)}")
        raise


# Send Login Verification email
@csrf_exempt
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