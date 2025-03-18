# home/signals.py

import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.apps import apps  # Import apps to use get_model
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender='home.QuePdf')  # Use string format to avoid circular import
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

@shared_task
def send_email_task(instance_id, instance_data):
    logger.info(f"Received instance_id: {instance_id}, instance_data: {instance_data}")  # Debugging task call

    try:
        QuePdf = apps.get_model('home', 'QuePdf')  # Dynamically get the model
        instance = QuePdf.objects.get(id=instance_id)  # Fetch the instance using the ID
        logger.info(f"Fetched instance: {instance}")  # Debugging instance fetching

        Profile = apps.get_model('home', 'Profile')  # Dynamically get the model
        matching_users = Profile.objects.filter(course=instance.course)
        if not matching_users.exists():
            logger.warning(f"No users found for course: {instance.course}")
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
                logger.info(f"Email sent to {user.user_obj.username} ({user.user_obj.email})")

            except Exception as e:
                logger.error(f"Failed to send email to {user.user_obj.username} ({user.user_obj.email}): {e}")

    except Exception as e:
        logger.error(f"Error fetching instance: {e}")