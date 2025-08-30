import logging
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Message
from Pixel.settings import EMAIL_HOST_USER
from django.contrib.auth.models import User

# ✅ Configure logger
logger = logging.getLogger(__name__)

@shared_task
def send_unseen_message_email_task(sender_id, receiver_id):
    try:
        receiver = User.objects.get(id=receiver_id)
        sender = User.objects.get(id=sender_id)

        unseen_msgs = Message.objects.filter(receiver=receiver, is_seen=False).order_by("created_at")
        chat_link = f"https://pixelclass.netlify.app/chat/{sender.username}"

        if unseen_msgs.exists():
            context = {
                "receiver_name": receiver.get_full_name() or receiver.username,
                "receiver_email": receiver.email,
                "unseen_count": unseen_msgs.count(),
                "messages": unseen_msgs,
                "latest_message": unseen_msgs.last(),
                "chat_link": chat_link,
            }

            html_message = render_to_string("unseen_msg/Unseen_Message.html", context)
            plain_message = strip_tags(html_message)

            send_mail(
                subject="📩 You have unread messages",
                message=plain_message,
                from_email=EMAIL_HOST_USER,
                recipient_list=[receiver.email],
                html_message=html_message,
            )
    except Exception as e:
        logger.error(f"Error while sending batched email: {e}", exc_info=True)
