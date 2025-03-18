import urllib.parse
import json
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.apps import apps  
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from celery import shared_task
from home.serializers import QuePdfSerializer  

@receiver(post_save, sender='home.QuePdf')  # Avoid circular import issues
def que_pdf_notification(sender, instance, created, **kwargs):
    """Trigger email notification when a new QuePdf instance is created."""
    if created:
        try:
            serializer = QuePdfSerializer(instance)  # Convert instance to JSON
            instance_data = serializer.data  

            # Add the PDF link
            instance_data["pdf_link"] = (
                f"https://pixelclass.netlify.app/ns?sub={urllib.parse.quote(str(instance.sub))}"
                f"&id={instance.id}&course={urllib.parse.quote(str(instance.course))}&choose=Assignment"
            )

            # Debug: Print JSON data being sent
            print(f"[DEBUG] QuePdf Created - Data Sent to Celery: {json.dumps(instance_data, indent=4)}")

            # Ensure `instance_data` is JSON serializable
            send_email_task.delay(json.dumps(instance_data))  # Serialize before passing to Celery

        except Exception as e:
            print(f"[ERROR] Failed to trigger email notification: {e}")

@shared_task
def send_email_task(instance_data_json):
    """Celery task to send an email notification asynchronously."""
    instance_data = json.loads(instance_data_json)  # Deserialize JSON string back to a dictionary
    print(f"[INFO] Processing email task for QuePdf ID: {instance_data['id']}")

    try:
        QuePdf = apps.get_model('home', 'QuePdf')  # Dynamically get the model
        instance = QuePdf.objects.get(id=instance_data['id'])  # Fetch the instance using the ID

        Profile = apps.get_model('home', 'Profile')  # Get Profile model
        matching_users = Profile.objects.filter(course=instance.course)

        if not matching_users.exists():
            print(f"[WARNING] No users found for course: {instance.course}")
            return  

        subject = "📄 New Assignment Available!"

        for user in matching_users:
            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': user.user_obj.username},
                    'pdf_link': instance_data["pdf_link"]
                }

                # Render email content
                html_message = render_to_string('que_pdf_notification/que_pdf_notification.html', context)
                plain_message = strip_tags(html_message)

                # Send email
                send_mail(
                    subject,
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user.user_obj.email],
                    html_message=html_message,
                    fail_silently=False
                )
                print(f"[SUCCESS] Email sent to {user.user_obj.username} ({user.user_obj.email})")

            except Exception as e:
                print(f"[ERROR] Failed to send email to {user.user_obj.username} ({user.user_obj.email}): {e}")

    except QuePdf.DoesNotExist:
        print(f"[ERROR] QuePdf instance with ID {instance_data['id']} not found.")

    except Exception as e:
        print(f"[ERROR] Unexpected error while processing email task: {e}")
