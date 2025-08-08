from celery import shared_task
from django.utils import timezone
from .models import Message
from django.core.mail import send_mail

@shared_task
def send_unseen_message_email_task(message_id):
    try:
        msg = Message.objects.get(id=message_id)
        if not msg.is_seen:
            send_mail(
                subject="You have an unread message",
                message=f"You have a new message from {msg.sender.username}: {msg.content}",
                from_email=None,
                recipient_list=[msg.receiver.email],
            )
    except Message.DoesNotExist:
        pass
