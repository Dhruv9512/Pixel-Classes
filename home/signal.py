import os
import json
import logging
import urllib.parse

# Django & Celery Imports
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from celery import shared_task

# Local App Imports
from .models import QuePdf
from Profile.models import profile

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
    logger.info("Brevo API client configured successfully for PDF notifications.")

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
# HELPER FUNCTION (NO CHANGES)
# ==============================================================================
def _heading_for_choose(choose):
    if choose == "exam_paper":
        return "Exam Paper"
    if choose == "important_notes":
        return "Important Notes"
    return choose

# ==============================================================================
# UPDATED CELERY TASK
# ==============================================================================
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_email_task(self, instance_data):
    """Celery task to send bulk email notifications using the reusable helper."""
    try:
        if not isinstance(instance_data, dict):
            logger.error(f"Received unexpected data format: {type(instance_data)}")
            return

        qid = instance_data.get('id')
        logger.info(f"Processing email task for QuePdf ID: {qid}")

        instance = QuePdf.objects.only('course', 'choose').filter(id=qid).first()
        if not instance:
            logger.error(f"QuePdf instance with ID {qid} not found.")
            return

        matching_users = profile.objects.filter(course=instance.course).select_related('user_obj').only('user_obj__email', 'user_obj__username')
        if not matching_users.exists():
            logger.warning(f"No users found matching course: {instance.course}. Task finished.")
            return

        heading = _heading_for_choose(instance.choose)
        pdf_link = instance_data.get("pdf_link", "")
        subject = f"📝 New {heading} PDF Available!"
        
        logger.info(f"Found {matching_users.count()} users to notify for course '{instance.course}'.")

        for prof in matching_users:
            user_obj = prof.user_obj
            user_email = getattr(user_obj, "email", None)
            username = getattr(user_obj, "username", "User")
            
            if not user_email:
                logger.warning(f"Skipping user {username} due to missing email.")
                continue

            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': username},
                    'pdf_link': pdf_link,
                    'heading': heading,
                }
                _send_templated_email(
                    subject=subject,
                    to_email=user_email,
                    html_template='que_pdf_notification/que_pdf_notification.html',
                    context=context,
                    plain_fallback=f"Hello {username}, a new {heading} has been uploaded for your course. View it here: {pdf_link}"
                )
            except Exception as e:
                # Log the error for the specific user but continue the loop
                logger.error(f"Failed to send notification to {user_email}. Error: {e}")

    except Exception as e:
        logger.exception(f"A critical error occurred in the email task for QuePdf ID {instance_data.get('id')}. Celery will retry.")
        raise self.retry(exc=e)

# ==============================================================================
# SIGNAL RECEIVER (NO CHANGES NEEDED, LOGGING IMPROVED)
# ==============================================================================
@receiver(post_save, sender='home.QuePdf')
def que_pdf_notification(sender, instance, created, **kwargs):
    """Trigger email notification when a new QuePdf instance is created."""
    if created:
        try:
            from home.serializers import QuePdfSerializer
            serializer = QuePdfSerializer(instance)
            instance_data = serializer.data

            sem = str(getattr(instance, 'sem', ''))
            sub = str(getattr(instance, 'sub', ''))
            instance_data["pdf_link"] = (
                "https://pixelclass.netlify.app/"
                f"{urllib.parse.quote(sem)}/"
                f"{urllib.parse.quote(sub)}"
            )

            logger.debug(f"QuePdf Created - Data to be sent to Celery: {json.dumps(instance_data)}")

            if instance.id:
                send_email_task.apply_async(args=[instance_data])
                logger.info(f"Dispatched Celery task 'send_email_task' for QuePdf ID: {instance.id}")
            else:
                logger.error("Instance ID is missing after save, cannot dispatch Celery task.")

        except Exception as e:
            logger.exception(f"Failed to trigger email notification task for QuePdf: {e}")