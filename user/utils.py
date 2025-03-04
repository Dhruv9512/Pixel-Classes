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
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from home.models import AnsPdf



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
    # Generate token
    token = default_token_generator.make_token(user)

    # Set token expiration date (1 hour from now)
    expiry_date = timezone.now() + timedelta(hours=1)

    # Save the token in the database
    password_reset_token = PasswordResetToken(
        user=user,
        token=token,
        expiry_date=expiry_date
    )
    password_reset_token.save()

    return token
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
        context1 = {
            'username': user.username,
            'otp': otp,
        }
        return Response(context1, status=status.HTTP_200_OK)
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


# reset password mail
@csrf_exempt
def send_password_reset_email(user,url):
    """
    Sends a password reset email to the user with a link to reset their password.
    """
    # Set email subject
    subject = "Password Reset Request"
    
    # Render the email body from the template with context variables
    message = render_to_string(
        'reset_password/send_password_reset_email.html',
        {'url': url, 'username': user.username}
    )

    try:
        # Send the email (using the default email address in Django settings)
        send_mail(
            subject,
            message,
            EMAIL_HOST_USER,  # Email address from settings
            [user.email],  # Recipient email address
            html_message=message  # HTML message version
        )
        logger.info(f"Sent password reset email to {user.email}")
    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {str(e)}")


# Send password reset confirmation email
@csrf_exempt
def send_password_reset_confirmation(user):
    subject = "Password Reset Successful"

    message = render_to_string(
        'reset_password_success/reset_password_success.html',
        {'url': "https://pixelclass.netlify.app/login", 'username': user.username , 'current_year': now().year}
    )
        
    try:
        # Send the email (using the default email address in Django settings)
        send_mail(
            subject,
            message,
            EMAIL_HOST_USER,  # Email address from settings
            [user.email],  # Recipient email address
            html_message=message  # HTML message version
        )
        logger.info(f"Sent password reset email to {user.email}")
    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {str(e)}")



# Path: user/signals.py
User = get_user_model()  

@receiver(post_save, sender=AnsPdf)
def send_email_notification(sender, instance, created, **kwargs):
    if created:  # If a new row is created in the AnsPdf table
        subject = "New PDF Uploaded!"
        message = f"A new PDF has been uploaded: {instance}\nCheck it out now!"
        
        
        # recipients = list(User.objects.filter(is_active=True).values_list('email', flat=True))
        recipients = ['dhruvsharma56780@gmail.com']
        if recipients: 
            send_mail(subject, message, settings.EMAIL_HOST_USER, recipients)