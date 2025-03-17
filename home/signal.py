# home/signals.py

import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from home.models import QuePdf
from home.tasks import send_email_task  # Import Celery task

@receiver(post_save, sender=QuePdf)
def que_pdf_notification(sender, instance, created, **kwargs):
    if created:
        instance_data = {
            "id": instance.id,
            "course": str(instance.course),
            "sub": str(instance.sub),
            "sem": str(instance.sem) if instance.sem else "N/A",
            "year": str(instance.year) if instance.year else "N/A",
            "div": str(instance.div) if instance.div else "N/A",
            "pdf_link": f"https://pixelclass.netlify.app/ns?sub={urllib.parse.quote(str(instance.sub))}&id={instance.id}&course={urllib.parse.quote(str(instance.course))}&choose=Assignment"
        }
        print(f"About to call send_email_task with ID: {instance.id} and data: {instance_data}")
        send_email_task.delay(instance.id, instance_data)

# home/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from home.models import QuePdf, profile

@shared_task
def send_email_task(instance_id, instance_data):
    print(f"Received instance_id: {instance_id}, instance_data: {instance_data}")  # Debugging task call

    try:
        instance = QuePdf.objects.get(id=instance_id)
        print(f"Fetched instance: {instance}")  # Debugging instance fetching

        matching_users = profile.objects.filter(course=instance.course)
        if not matching_users.exists():
            print(f"No users found for course: {instance.course}")
            return  

        subject = "📄 New Que PDF Added!"
        for user in matching_users:
            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': user.user_obj.username},
                    'pdf_link': instance_data["pdf_link"]
                }

                html_message = render_to_string('que_pdf_notification/que_pdf_notification.html', context)
                plain_message = strip_tags(html_message)

                send_mail(
                    subject,
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user.user_obj.email],
                    html_message=html_message,
                    fail_silently=False
                )
                print(f"Email sent to {user.user_obj.username} ({user.user_obj.email})")

            except Exception as e:
                print(f"Failed to send email to {user.user_obj.username} ({user.user_obj.email}): {e}")

    except Exception as e:
        print(f"Error fetching instance: {e}")