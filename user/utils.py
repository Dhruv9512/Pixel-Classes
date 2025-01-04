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
    message = "Your password has been successfully reset."
    from_email = EMAIL_HOST_USER  # Use the email defined in your settings
    recipient_list = [user.email]  # Recipient is the user's email

    try:
        send_mail(subject, message, from_email, recipient_list)
        # Log success if needed
        logger.info(f"Password reset confirmation email sent to {user.email}")
    except Exception as e:
        # Log failure if needed
        logger.error(f"Error sending password reset confirmation email to {user.email}: {str(e)}")