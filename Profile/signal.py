import logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Follow
from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task
def send_follow_notification_task(instance_data):
    logger.info("📨 Celery Task Started: send_follow_notification_task")

    subject = "New Follower Alert!"
    recipient_email = instance_data.get('recipient_email')
    logger.info(f"📧 Sending to: {recipient_email}")

    try:
        html_message = render_to_string('Following/following.html', instance_data)
        plain_message = strip_tags(html_message)

        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info("✅ Email sent successfully")
    except Exception as e:
        logger.exception(f"❌ Error sending email to {recipient_email}: {e}")


@receiver(m2m_changed, sender=Follow.following.through)
def send_follow_notification(sender, instance, action, **kwargs):
    logger.info("🔔 Signal triggered for Follow model")

    if action == "post_add":
        follower = instance.user
        for user in instance.following.all():
            recipient_email = user.email
            logger.info(f"📧 Preparing to email: {recipient_email}")

            context = {
                'follower_username': follower.username,
                'following_username': user.username,
                'profile_url': f"https://pixelclass.netlify.app/profile?username={follower.username}/",
                'follower': follower.username,
                'following': user.username,
                'recipient_email': recipient_email,
            }

            try:
                send_follow_notification_task.apply_async(args=[context])
                logger.info("🚀 Celery task dispatched")
            except Exception as e:
                logger.exception(f"❌ Failed to dispatch Celery task: {e}")
