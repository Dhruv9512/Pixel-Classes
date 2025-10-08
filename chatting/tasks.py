import os
import logging
from celery import shared_task
from django.template.loader import render_to_string
from django.core.cache import cache
from django.contrib.auth.models import User
from .models import Message

# Brevo API client imports
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Set up a logger for this module
logger = logging.getLogger(__name__)

# ==============================================================================
# BREVO API CLIENT CONFIGURATION
# This setup is done once when the Celery worker starts for better performance.
# ==============================================================================

# Ensure these environment variables are set: BREVO_API_KEY, BREVO_SENDER_EMAIL
DEFAULT_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL')
DEFAULT_SENDER_NAME = "PixelClasses"  # You can customize the sender name here

# Configure the Brevo API client
configuration = sib_api_v3_sdk.Configuration()
brevo_api_key = os.getenv('BREVO_API_KEY')

if not brevo_api_key or not DEFAULT_SENDER_EMAIL:
    logger.critical("FATAL: BREVO_API_KEY or BREVO_SENDER_EMAIL environment variable not found. Email sending will fail.")
else:
    configuration.api_key['api-key'] = brevo_api_key
    logger.info("Brevo API client configured successfully for unseen message tasks.")

# Create a shared API instance
api_client = sib_api_v3_sdk.ApiClient(configuration)
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)


# ==============================================================================
# REUSABLE EMAIL SENDING HELPER
# ==============================================================================

def _send_templated_email(*, subject: str, to_email: str, html_template: str, context: dict, plain_fallback: str):
    """
    Renders and sends a transactional email using the global Brevo API instance.
    """
    if not configuration.api_key.get('api-key'):
        logger.error("Cannot send email because Brevo API key is not configured.")
        raise ValueError("Brevo API key is missing.")

    html_message = render_to_string(html_template, context or {})
    sender = {"name": DEFAULT_SENDER_NAME, "email": DEFAULT_SENDER_EMAIL}
    to = [{"email": to_email}]

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=to,
        sender=sender,
        subject=subject,
        html_content=html_message,
        text_content=plain_fallback
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        logger.info(f"Email '{subject}' sent to {to_email} via Brevo. Message ID: {api_response.message_id}")
    except ApiException as e:
        logger.error(f"Brevo API error when sending email to {to_email}: {e.body}")
        raise e


# ==============================================================================
# UPDATED CELERY TASK
# ==============================================================================

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_unseen_message_email_task(self, sender_id, receiver_id):
    """Sends a notification for unseen messages using the reusable email helper."""
    try:
        receiver = User.objects.only('id', 'username', 'first_name', 'email').get(id=receiver_id)
        sender = User.objects.only('id', 'username').get(id=sender_id)

        unseen_msgs = list(
            Message.objects
            .filter(receiver_id=receiver.id, sender_id=sender.id, is_seen=False)
            .order_by("timestamp")
        )

        if not unseen_msgs:
            logger.info(f"No unseen messages found from sender {sender_id} to receiver {receiver_id}. Task ending.")
            return

        unseen_count = len(unseen_msgs)
        receiver_name = receiver.get_full_name() or receiver.username
        subject = f"📩 You have {unseen_count} unread message(s) from {sender.username}"

        context = {
            "receiver_name": receiver_name,
            "unseen_count": unseen_count,
            "messages": unseen_msgs,
            "latest_message": unseen_msgs[-1],
            "sender_username": sender.username
        }
        
        # Use the reusable helper to send the email
        _send_templated_email(
            subject=subject,
            to_email=receiver.email,
            html_template="unseen_msg/Unseen_Message.html",
            context=context,
            plain_fallback=f"Hello {receiver_name}, you have {unseen_count} unread messages from {sender.username}."
        )

        # Clear cache lock after successful dispatch
        cache.delete(f"email_scheduled_receiver_{receiver.id}")
        logger.info(f"Successfully processed unseen message email for {receiver.email}.")

    except User.DoesNotExist:
        logger.warning(f"User with sender_id={sender_id} or receiver_id={receiver_id} not found. Task will not be retried.")
        # Do not re-raise, as this is not a transient error
    except Exception as e:
        logger.error(f"Error while sending unseen message email: {e}", exc_info=True)
        # Re-raise the exception to allow Celery to handle the retry
        raise self.retry(exc=e)