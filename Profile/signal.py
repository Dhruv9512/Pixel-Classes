from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Follow
from celery import shared_task


@shared_task
def send_follow_notification_task(instance_data):
    print("📨 Celery Task Started: send_follow_notification_task")

    subject = "New Follower Alert!"
    recipient_email = instance_data.get('recipient_email')
    print(f"📧 Sending to: {recipient_email}")

    try:
        print("📦 Context:")
        for key, value in instance_data.items():
            print(f"  {key}: {value}")

        html_message = render_to_string('Following/following.html', instance_data)
        plain_message = strip_tags(html_message)

        print("🧾 Rendered Email Preview (First 200 chars):")
        print(html_message[:200])

        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        print("✅ Email sent successfully")

    except Exception as e:
        print(f"❌ Error sending email: {e}")


@receiver(post_save, sender=Follow)
def send_follow_notification(sender, instance, created, **kwargs):
    print("🔔 Signal triggered for Follow model")

    if created:
        print("✅ New Follow instance created")

        follower = instance.user
        following = instance.following

        if not follower or not following:
            print("❌ Missing follower or following user")
            return

        recipient_email = following.email
        print(f"📧 Email will be sent to: {recipient_email}")

        context = {
            'follower_username': follower.username,
            'following_username': following.username,
            'profile_url': f"https://pixelclass.netlify.app/profile?username={follower.username}/",
            'follower': follower.username,
            'following': following.username,
            'recipient_email': recipient_email,
            'log': '📦 Task triggered and context prepared',  # Optional log in template
        }

        print(f"📦 Context ready: {context}")

        try:
            send_follow_notification_task.apply_async(args=[context])
            print("🚀 Celery task dispatched successfully")
        except Exception as e:
            print(f"❌ Failed to dispatch Celery task: {e}")
    else:
        print("ℹ️ Follow instance updated (not new)")
