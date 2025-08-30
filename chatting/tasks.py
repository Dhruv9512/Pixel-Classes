import logging
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Message
from Pixel.settings import EMAIL_HOST_USER
from django.contrib.auth.models import User
from django.core.cache import cache

# ✅ Configure logger
logger = logging.getLogger(__name__)

@shared_task
def send_unseen_message_email_task(sender_id, receiver_id):
    try:
        receiver = User.objects.get(id=receiver_id)
        sender = User.objects.get(id=sender_id)

        # ✅ Filter unseen messages from the specific sender
        unseen_msgs = Message.objects.filter(
            receiver=receiver,
            sender=sender,
            is_seen=False
        ).order_by("timestamp")

        if unseen_msgs.exists():
            context = {
                "receiver_name": receiver.get_full_name() or receiver.username,
                "receiver_email": receiver.email,
                "unseen_count": unseen_msgs.count(),
                "messages": unseen_msgs,
                "latest_message": unseen_msgs.last(),
            }

            html_message = render_to_string("unseen_msg/Unseen_Message.html", context)
            plain_message = strip_tags(html_message)

            send_mail(
                message=plain_message,
                from_email=EMAIL_HOST_USER,
                recipient_list=[receiver.email],
                html_message=html_message,
            )
            # ✅ Remove lock so new messages can schedule next email
            cache.delete(f"email_scheduled_receiver_{receiver.id}")
    except Exception as e:
        logger.error(f"Error while sending batched email: {e}", exc_info=True)
