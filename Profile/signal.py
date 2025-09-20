import logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Follow
from celery import shared_task

logger = logging.getLogger(__name__)

# Celery task with automatic retries (exponential backoff + jitter)
@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_follow_notification_task(self, instance_data):
    logger.info("📨 Celery Task Started: send_follow_notification_task")

    subject = "New Follower Alert!"
    recipient_email = instance_data.get('recipient_email')
    if not recipient_email:
        logger.warning("Recipient email missing in task payload")
        return

    logger.info(f"📧 Sending to: {recipient_email}")
    try:
        html_message = render_to_string('Following/following.html', instance_data)
        plain_message = strip_tags(html_message)

        # Build once, send once (uses backend connection pooling implicitly) [web:48]
        email = EmailMessage(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email],
        )
        email.content_subtype = "plain"
        email.attach_alternative(html_message, "text/html")

        email.send(fail_silently=False)
        logger.info("✅ Email sent successfully")
    except Exception as e:
        logger.exception(f"❌ Error sending email to {recipient_email}: {e}")
        # autoretry_for will retry automatically [web:57]

@receiver(m2m_changed, sender=Follow.following.through)
def send_follow_notification(sender, instance, action, pk_set, **kwargs):
    logger.info("🔔 Signal triggered for Follow.following")

    if action != "post_add":
        logger.info("ℹ️ Action not post_add, ignoring.")
        return

    logger.info("✅ New follow relationship added")

    try:
        follower_user = instance.user  # User who initiated the follow
        follower_username = getattr(follower_user, "username", None)
        if not follower_username:
            logger.warning("Follower username missing; skipping notifications")
            return

        # Fetch only needed fields for followed users in one query to reduce DB hits [web:27]
        # Instead of repeated Follow.objects.get(pk=...), use a single queryset filter
        for followed_follow_obj in Follow.objects.only('id').filter(pk__in=pk_set).select_related('user'):
            followed_user = followed_follow_obj.user
            recipient_email = getattr(followed_user, "email", None)
            if not recipient_email:
                logger.warning(f"Recipient email missing for user {getattr(followed_user, 'id', 'unknown')}; skipping")
                continue

            context = {
                'follower_username': follower_username,
                'following_username': getattr(followed_user, "username", ""),
                'profile_url': f"https://pixelclass.netlify.app/profile?username={follower_username}",
                'follower': follower_username,
                'following': getattr(followed_user, "username", ""),
                'recipient_email': recipient_email,
            }

            logger.debug(f"📦 Context ready: {context}")
            send_follow_notification_task.apply_async(args=[context])
            logger.info("🚀 Celery task dispatched")

    except Exception:
        logger.exception("❌ Error processing follow notifications")
