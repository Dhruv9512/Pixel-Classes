# your_app/tasks.py

import logging
from celery import shared_task
from django.conf import settings  # Import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Message
from django.contrib.auth.models import User
from django.core.cache import cache

# Import Brevo SDK
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_unseen_message_email_task(self, sender_id, receiver_id):
    try:
        # Fetch users (no changes here)
        receiver = User.objects.only('id', 'username', 'first_name', 'last_name', 'email').get(id=receiver_id)
        sender = User.objects.only('id', 'username').get(id=sender_id)

        # Fetch messages (no changes here)
        unseen_qs = (
            Message.objects
            .filter(receiver_id=receiver.id, sender_id=sender.id, is_seen=False)
            .order_by("timestamp")
        )
        unseen_msgs = list(unseen_qs)

        if unseen_msgs:
            latest_message = unseen_msgs[-1]
            unseen_count = len(unseen_msgs)

            # Prepare context and render template (no changes here)
            context = {
                "receiver_name": receiver.get_full_name() or receiver.username,
                "receiver_email": receiver.email,
                "unseen_count": unseen_count,
                "messages": unseen_msgs,
                "latest_message": latest_message,
            }
            html_message = render_to_string("unseen_msg/Unseen_Message.html", context)

            # ==================================================================
            # START: MODIFIED CODE BLOCK
            # ==================================================================
            # Configure the Brevo API client
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = settings.BREVO_API_KEY
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

            # Define sender, receiver, and create the email payload
            subject = f"📩 You have unread messages from {sender.username}"
            sender_info = {"email": settings.DEFAULT_FROM_EMAIL, "name": "PixelClasses"} # Customize sender name
            to_info = [{"email": receiver.email, "name": receiver.get_full_name() or receiver.username}]
            
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                to=to_info,
                sender=sender_info,
                subject=subject,
                html_content=html_message
            )

            # Send the email via Brevo API
            api_instance.send_transac_email(send_smtp_email)
            logger.info(f"Successfully sent unseen message email to {receiver.email} via Brevo.")
            # ==================================================================
            # END: MODIFIED CODE BLOCK
            # ==================================================================

            # Clear cache lock (no changes here)
            cache.delete(f"email_scheduled_receiver_{receiver.id}")

    except User.DoesNotExist:
        logger.warning(f"User with sender_id={sender_id} or receiver_id={receiver_id} not found. Task will not be retried.")
        # Do not re-raise, as this is not a transient error
    except Exception as e:
        logger.error(f"Error while sending unseen message email: {e}", exc_info=True)
        # Re-raise the exception to allow Celery to handle the retry
        raise e