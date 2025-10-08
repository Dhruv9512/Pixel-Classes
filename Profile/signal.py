import logging
import os

# Django & Celery Imports
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.template.loader import render_to_string
from celery import shared_task

# Local Imports
from .models import Follow

# Brevo API client imports
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Set up a logger for this module
logger = logging.getLogger(__name__)

# ==============================================================================
# BREVO API CLIENT CONFIGURATION
# This setup is done once when the Celery worker starts, making it more efficient.
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
    logger.info("Brevo API client configured successfully for signals.")

# Create a shared API instance
api_client = sib_api_v3_sdk.ApiClient(configuration)
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)


# ==============================================================================
# REUSABLE EMAIL SENDING HELPER
# ==============================================================================

def _send_templated_email(*, subject: str, to_email: str, html_template: str, context: dict, plain_fallback: str):
    """
    A helper function to render and send a transactional email using the global Brevo API instance.
    """
    if not configuration.api_key.get('api-key'):
        logger.error("Cannot send email because Brevo API key is not configured.")
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
# UPDATED CELERY TASK
# This task now uses the reusable helper function.
# ==============================================================================
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_follow_notification_task(self, instance_data):
    """
    Sends a "New Follower" notification email by calling the helper function.
    """
    logger.info("📨 Celery Task Started: send_follow_notification_task")

    recipient_email = instance_data.get('recipient_email')
    follower_username = instance_data.get('follower_username', 'Someone')

    if not recipient_email:
        logger.warning("Recipient email missing in task payload. Aborting.")
        return

    try:
        logger.info(f"📧 Preparing to send follow notification to: {recipient_email}")
        _send_templated_email(
            subject="New Follower Alert!",
            to_email=recipient_email,
            html_template='Following/following.html',
            context=instance_data,
            plain_fallback=f"Hi {instance_data.get('following_username', '')},\n\n{follower_username} is now following you on PixelClasses!"
        )
        logger.info(f"✅ Follow notification queued successfully for {recipient_email}")

    except Exception as e:
        logger.exception(f"❌ Failed to queue follow notification for {recipient_email}. Error: {e}")
        # Re-raise the exception to trigger Celery's automatic retry mechanism
        raise self.retry(exc=e)


# ==============================================================================
# SIGNAL RECEIVER (NO CHANGES NEEDED)
# This function correctly prepares data and dispatches the task.
# ==============================================================================
@receiver(m2m_changed, sender=Follow.following.through)
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    logger.info("🔔 Signal triggered for Follow.following")

    if action != "post_add":
        logger.info(f"ℹ️ Action is '{action}', not 'post_add'. Ignoring.")
        return

    logger.info("✅ New follow relationship added. Preparing to dispatch task.")

    try:
        follower_user = instance.user  # User who initiated the follow
        follower_username = getattr(follower_user, "username", None)

        if not follower_username:
            logger.warning("Follower username missing; cannot send notifications.")
            return

        # Query for the user being followed
        for followed_user_pk in pk_set:
            try:
                # Assuming the pk_set contains user IDs being followed
                followed_user = Follow.objects.get(pk=followed_user_pk).user
                recipient_email = getattr(followed_user, "email", None)
                
                if not recipient_email:
                    logger.warning(f"Recipient email missing for followed user ID {followed_user_pk}; skipping.")
                    continue

                context = {
                    'follower_username': follower_username,
                    'following_username': getattr(followed_user, "username", ""),
                    'profile_url': f"https://pixelclass.netlify.app/profile?username={follower_username}",
                    'recipient_email': recipient_email, # Pass for logging within the task
                }

                logger.debug(f"📦 Context ready for {recipient_email}: {context}")
                
                # Dispatch the updated Celery task
                send_follow_notification_task.apply_async(args=[context])
                logger.info(f"🚀 Celery task dispatched for new follower notification to {recipient_email}")

            except Follow.DoesNotExist:
                 logger.warning(f"Follow object with pk={followed_user_pk} not found. Skipping.")
            except Exception as e:
                 logger.error(f"Error processing notification for pk={followed_user_pk}: {e}")

    except Exception as e:
        logger.exception(f"❌ A critical error occurred in the send_follow_notification signal handler: {e}")