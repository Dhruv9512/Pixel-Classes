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
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    logger.info("🔔 Signal triggered for Follow.following")

    if action == "post_add":
        logger.info("✅ New follow relationship added")

        try:
            follower_user = instance.user  # User who initiated the follow
            for followed_follow_id in pk_set:
                try:
                    # This gets the Follow object being followed
                    followed_follow_obj = Follow.objects.get(pk=followed_follow_id)
                    followed_user = followed_follow_obj.user  # The actual User instance

                    recipient_email = followed_user.email
                    logger.info(f"📧 Email will be sent to: {recipient_email}")

                    context = {
                        'follower_username': follower_user.username,
                        'following_username': followed_user.username,
                        'profile_url': f"https://pixelclass.netlify.app/profile?username={follower_user.username}",
                        'follower': follower_user.username,
                        'following': followed_user.username,
                        'recipient_email': recipient_email,
                    }

                    logger.debug(f"📦 Context ready: {context}")
                    send_follow_notification_task.apply_async(args=[context])
                    logger.info("🚀 Celery task dispatched")

                except Exception as e:
                    logger.exception("❌ Error processing followed user")

        except Exception as e:
            logger.exception("❌ Error processing follower user")
    else:
        logger.info("ℹ️ Action not post_add, ignoring.")
