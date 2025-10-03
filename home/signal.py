# your_app/signals.py (or wherever this code lives)

import json
import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from .models import QuePdf
from Profile.models import profile

# Import Brevo SDK
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

# Helper function (no changes needed)
def _heading_for_choose(choose):
    if choose == "exam_paper":
        return "Exam Paper"
    if choose == "important_notes":
        return "Important Notes"
    return choose

# ==============================================================================
# UPDATED CELERY TASK
# This is the only function that needs to be modified.
# ==============================================================================
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_email_task(self, instance_data):
    """Celery task to send email notifications using the Brevo API."""
    try:
        if not isinstance(instance_data, dict):
            print(f"[ERROR] Received unexpected data format: {type(instance_data)}")
            return

        qid = instance_data.get('id')
        print(f"[INFO] Processing Brevo email task for QuePdf ID: {qid}")

        instance = QuePdf.objects.only('id', 'course', 'choose', 'sem', 'sub').filter(id=qid).first()
        if not instance:
            print(f"[ERROR] QuePdf instance with ID {qid} not found.")
            return

        matching_users = (
            profile.objects
            .select_related('user_obj')
            .only('id', 'course', 'user_obj__id', 'user_obj__username', 'user_obj__email')
            .filter(course=instance.course)
        )
        if not matching_users.exists():
            print(f"[WARNING] No users found for course: {instance.course}")
            return

        heading = _heading_for_choose(instance.choose)
        pdf_link = instance_data.get("pdf_link", "")
        subject = f"📝 New {heading} PDF Available!"

        # Configure the Brevo API client ONCE for this task run
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
        sender = {"email": settings.DEFAULT_FROM_EMAIL, "name": "PixelClasses"} # Customize sender name

        # Loop through each user and send an email
        for prof in matching_users:
            user_obj = prof.user_obj
            user_email = getattr(user_obj, "email", None)
            if not user_email:
                print(f"[WARNING] Skipping user {getattr(user_obj, 'username', 'unknown')} due to missing email.")
                continue

            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': getattr(user_obj, "username", "User")},
                    'pdf_link': pdf_link,
                    'heading': heading,
                }
                html_message = render_to_string('que_pdf_notification/que_pdf_notification.html', context)
                
                # Create the email payload for this specific user
                to = [{"email": user_email, "name": getattr(user_obj, "username", "User")}]
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=to,
                    sender=sender,
                    subject=subject,
                    html_content=html_message
                )

                # Send the email via Brevo API
                api_instance.send_transac_email(send_smtp_email)
                print(f"[SUCCESS] Brevo email sent to {getattr(user_obj, 'username', '')} ({user_email})")

            except ApiException as e:
                # Log API-specific errors, but let the loop continue for other users
                print(f"[ERROR] Brevo API Error for {user_email}: {e}")
            except Exception as e:
                print(f"[ERROR] Failed to send email to {user_email}: {e}")

    except Exception as e:
        print(f"[ERROR] Unexpected error in email task. Celery will retry. Error: {e}")
        # Re-raise the exception to allow Celery to handle the retry
        raise e

# ==============================================================================
# SIGNAL RECEIVER (NO CHANGES NEEDED HERE)
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
                f"/{urllib.parse.quote(sem)}"
                f"/{urllib.parse.quote(sub)}"
            )

            print(f"[DEBUG] QuePdf Created - Data Sent to Celery: {json.dumps(instance_data, indent=4)}")

            if instance.id:
                send_email_task.apply_async(args=[instance_data])
            else:
                print("[ERROR] Instance ID is missing, not sending to Celery.")

        except Exception as e:
            print(f"[ERROR] Failed to trigger email notification: {e}")