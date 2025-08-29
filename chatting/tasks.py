import logging
from celery import shared_task
from django.core.mail import send_mail
from .models import Message

# ✅ Configure logger
logger = logging.getLogger(__name__)

@shared_task
def send_unseen_message_email_task(message_id):
    logger.info(f"Task started: send_unseen_message_email_task for message_id={message_id}")
    try:
        msg = Message.objects.get(id=message_id)
        logger.info(f"Message fetched: id={msg.id}, sender={msg.sender.username}, receiver={msg.receiver.username}, is_seen={msg.is_seen}")

        if not msg.is_seen:
            send_mail(
                subject="You have an unread message",
                message=f"You have a new message from {msg.sender.username}: {msg.content}",
                from_email=None,
                recipient_list=[msg.receiver.email],
            )
            logger.info(f"Email sent successfully to {msg.receiver.email} for message_id={msg.id}")
        else:
            logger.info(f"Message {msg.id} already seen. No email sent.")

    except Message.DoesNotExist:
        logger.warning(f"Message with id={message_id} does not exist.")
    except Exception as e:
        logger.error(f"Error while sending email for message_id={message_id}: {e}", exc_info=True)
