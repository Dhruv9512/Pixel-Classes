import json
import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps  
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from .models import QuePdf
from Profile.models import profile

@shared_task
def send_email_task(instance_data):
    """Celery task to send an email notification asynchronously."""
    try:
        if not isinstance(instance_data, dict):
            print(f"[ERROR] Received unexpected data format: {type(instance_data)}")
            return

        print(f"[INFO] Processing email task for QuePdf ID: {instance_data.get('id')}")

        instance = QuePdf.objects.filter(id=instance_data.get('id')).first()

        if not instance:
            print(f"[ERROR] QuePdf instance with ID {instance_data.get('id')} not found.")
            return  

       
        matching_users = profile.objects.filter(course=instance.course)

        if not matching_users.exists():
            print(f"[WARNING] No users found for course: {instance.course}")
            return  

        for user in matching_users:
            user_email = getattr(user.user_obj, "email", None)
            if not user_email:
                print(f"[WARNING] Skipping user {user.user_obj.username} due to missing email.")
                continue  
        

            if instance.choose == "exam_paper":
                heading = "Exam Paper"
            elif instance.choose == "important_notes":
                heading = "Important Notes"
            else:
                heading = instance.choose

            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': getattr(user.user_obj, "username", "User")},
                    'pdf_link': instance_data["pdf_link"],
                    'heading': heading
                }

                # Render email content
                html_message = render_to_string('que_pdf_notification/que_pdf_notification.html', context)
                plain_message = strip_tags(html_message)

                

                # Send email
                send_mail(
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user_email],
                    html_message=html_message,
                    fail_silently=False
                )
                print(f"[SUCCESS] Email sent to {user.user_obj.username} ({user_email})")

            except Exception as e:
                print(f"[ERROR] Failed to send email to {user.user_obj.username} ({user_email}): {e}")

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

            instance_data["pdf_link"] = (
                f"https://pixelclass.netlify.app/ns?"
                f"sub={urllib.parse.quote(str(getattr(instance, 'sub', '')))}"
                f"&id={instance.id}"
                f"&course={urllib.parse.quote(str(getattr(instance, 'course', '')))}"
                f"&choose={urllib.parse.quote(str(getattr(instance, 'choose', '')))}"
            )


            # Debugging
            print(f"[DEBUG] QuePdf Created - Data Sent to Celery: {json.dumps(instance_data, indent=4)}")

            if instance.id:
                send_email_task.apply_async(args=[instance_data])  # Pass dictionary directly
            else:
                print("[ERROR] Instance ID is missing, not sending to Celery.")

        except Exception as e:
            print(f"[ERROR] Failed to trigger email notification: {e}")
