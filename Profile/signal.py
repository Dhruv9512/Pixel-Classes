# your_app/signals.py

import logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.conf import settings
from django.template.loader import render_to_string
from .models import Follow
from celery import shared_task

# Import Brevo SDK
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

logger = logging.getLogger(__name__)

# ==============================================================================
# UPDATED CELERY TASK
# This is the only function that needs to be modified.
# ==============================================================================
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_follow_notification_task(self, instance_data):
    """
    Sends a "New Follower" notification email using the Brevo API.
    """
    logger.info("📨 Celery Task Started: send_follow_notification_task (using Brevo)")

    subject = "New Follower Alert!"
    recipient_email = instance_data.get('recipient_email')
    if not recipient_email:
        logger.warning("Recipient email missing in task payload")
        return

    logger.info(f"📧 Preparing Brevo email for: {recipient_email}")
    try:
        # 1. Render the HTML content from the template
        html_message = render_to_string('Following/following.html', instance_data)

        # 2. Configure the Brevo API client
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

        # 3. Define the sender and receiver
        sender = {"email": settings.DEFAULT_FROM_EMAIL, "name": "PixelClasses"} # Customize the sender name
        to = [{"email": recipient_email}]

        # 4. Create the email payload
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=to,
            sender=sender,
            subject=subject,
            html_content=html_message
        )

        # 5. Send the email
        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"✅ Email sent successfully via Brevo to {recipient_email}")

    except ApiException as e:
        logger.exception(f"❌ Brevo API Error sending email to {recipient_email}: {e}")
        # Re-raise exception to trigger Celery's automatic retry mechanism
        raise self.retry(exc=e)
    except Exception as e:
        logger.exception(f"❌ A general error occurred sending email to {recipient_email}: {e}")
        # Re-raise for Celery retry
        raise self.retry(exc=e)

# ==============================================================================
# SIGNAL RECEIVER (NO CHANGES NEEDED HERE)
# This function correctly prepares data and dispatches the task.
# ==============================================================================
@receiver(m2m_changed, sender=Follow.following.through)
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    logger.info("🔔 Signal triggered for Follow.following")

    if action != "post_add":
        logger.info("ℹ️ Action not post_add, ignoring.")
        return

    logger.info("✅ New follow relationship added")

    try:
        follower_user = instance.user  # User who initiated the follow
        follower_username = getattr(follower_user, "username", None)
        if not follower_username:
            logger.warning("Follower username missing; skipping notifications")
            return

        for followed_follow_obj in Follow.objects.only('id').filter(pk__in=pk_set).select_related('user'):
            followed_user = followed_follow_obj.user
            recipient_email = getattr(followed_user, "email", None)
            if not recipient_email:
                logger.warning(f"Recipient email missing for user {getattr(followed_user, 'id', 'unknown')}; skipping")
                continue

            context = {
                'follower_username': follower_username,
                'following_username': getattr(followed_user, "username", ""),
                'profile_url': f"https://pixelclass.netlify.app/profile?username={follower_username}",
                'follower': follower_username,
                'following': getattr(followed_user, "username", ""),
                'recipient_email': recipient_email,
            }

            logger.debug(f"📦 Context ready: {context}")
            # Dispatch the updated Celery task
            send_follow_notification_task.apply_async(args=[context])
            logger.info("🚀 Celery task dispatched")

    except Exception:
        logger.exception("❌ Error processing follow notifications")