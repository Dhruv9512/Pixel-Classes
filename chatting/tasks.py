import logging
from celery import shared_task
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Message
from Pixel.settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.core.cache import cache

logger = logging.getLogger(__name__)

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def send_unseen_message_email_task(self, sender_id, receiver_id):
    try:
        # Fetch minimal fields; avoid extra columns in logs [web:27]
        receiver = User.objects.only('id', 'username', 'first_name', 'last_name', 'email').get(id=receiver_id)
        sender = User.objects.only('id', 'username').get(id=sender_id)

        # Single queryset, evaluate once; avoid .exists() + .count() + .last() multiple hits. [web:140][web:36]
        unseen_qs = (
            Message.objects
            .filter(receiver_id=receiver.id, sender_id=sender.id, is_seen=False)
            .order_by("timestamp")
        )

        # Evaluate once into list to reuse for count and last without extra queries. [web:140]
        unseen_msgs = list(unseen_qs)
        if unseen_msgs:
            latest_message = unseen_msgs[-1]
            unseen_count = len(unseen_msgs)

            context = {
                "receiver_name": receiver.get_full_name() or receiver.username,
                "receiver_email": receiver.email,
                "unseen_count": unseen_count,
                "messages": unseen_msgs,
                "latest_message": latest_message,
            }

            html_message = render_to_string("unseen_msg/Unseen_Message.html", context)
            plain_message = strip_tags(html_message)

            # Reuse one SMTP connection for the send (lower overhead) [web:48]
            with get_connection() as connection:
                email = EmailMessage(
                    subject=f"📩 You have unread messages from {sender.username}",
                    body=plain_message,
                    from_email=EMAIL_HOST_USER,
                    to=[receiver.email],
                    connection=connection,
                )
                email.content_subtype = "plain"
                email.attach_alternative(html_message, "text/html")
                email.send(fail_silently=False)

            # Keep same cache lock behavior
            cache.delete(f"email_scheduled_receiver_{receiver.id}")

    except Exception as e:
        logger.error(f"Error while sending batched email: {e}", exc_info=True)
