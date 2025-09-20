import json
import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from .models import QuePdf
from Profile.models import profile

# Helper: map choose to a user-friendly heading (same logic, faster than repeated if/elif)
def _heading_for_choose(choose):
    if choose == "exam_paper":
        return "Exam Paper"
    if choose == "important_notes":
        return "Important Notes"
    return choose

# Celery task: auto-retry with exponential backoff and jitter; reuse one SMTP connection
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_email_task(self, instance_data):
    """Celery task to send an email notification asynchronously."""
    try:
        if not isinstance(instance_data, dict):
            print(f"[ERROR] Received unexpected data format: {type(instance_data)}")
            return

        qid = instance_data.get('id')
        print(f"[INFO] Processing email task for QuePdf ID: {qid}")

        # Fetch only fields needed; fail fast if missing [web:27]
        instance = QuePdf.objects.only('id', 'course', 'choose', 'sem', 'sub').filter(id=qid).first()
        if not instance:
            print(f"[ERROR] QuePdf instance with ID {qid} not found.")
            return

        # Batch fetch matching users with minimal columns and join to user for email [web:27]
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

        # One SMTP connection for all emails in this batch (same behavior, less overhead) [web:48]
        with get_connection() as connection:
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
                    plain_message = strip_tags(html_message)

                    subject = f"📝 New {heading} PDF Available!"
                    email = EmailMessage(
                        subject=subject,
                        body=plain_message,
                        from_email=settings.EMAIL_HOST_USER,
                        to=[user_email],
                        connection=connection,  # reuse connection [web:48]
                    )
                    email.content_subtype = "plain"
                    email.attach_alternative(html_message, "text/html")
                    email.send(fail_silently=False)
                    print(f"[SUCCESS] Email sent to {getattr(user_obj, 'username', '')} ({user_email})")

                except Exception as e:
                    print(f"[ERROR] Failed to send email to {getattr(user_obj, 'username', '')} ({user_email}): {e}")

    except Exception as e:
        print(f"[ERROR] Unexpected error while processing email task: {e}")

@receiver(post_save, sender='home.QuePdf')
def que_pdf_notification(sender, instance, created, **kwargs):
    """Trigger email notification when a new QuePdf instance is created."""
    if created:
        try:
            from home.serializers import QuePdfSerializer

            serializer = QuePdfSerializer(instance)
            instance_data = serializer.data

            # Preserve link shape; avoid repeated getattr by local vars
            sem = str(getattr(instance, 'sem', ''))
            sub = str(getattr(instance, 'sub', ''))
            instance_data["pdf_link"] = (
                "https://pixelclass.netlify.app/"
                f"/{urllib.parse.quote(sem)}"
                f"/{urllib.parse.quote(sub)}"
            )

            print(f"[DEBUG] QuePdf Created - Data Sent to Celery: {json.dumps(instance_data, indent=4)}")

            if instance.id:
                # Fire and forget: pass the dict payload
                send_email_task.apply_async(args=[instance_data])
            else:
                print("[ERROR] Instance ID is missing, not sending to Celery.")

        except Exception as e:
            print(f"[ERROR] Failed to trigger email notification: {e}")
