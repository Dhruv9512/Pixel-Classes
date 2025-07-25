from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Follow
from django.contrib.auth.models import User

@receiver(post_save, sender=Follow)
def send_follow_notification(sender, instance, created, **kwargs):
    if created:
        follower = instance.user
        following = instance.following
        recipient_email = following.email

        subject = "New Follower Alert!"

        # ✅ Define context here
        context = {
            'follower_username': follower.username,
            'following_username': following.username,
            'profile_url': f"https://pixelclass.netlify.app/profile?username={follower.username}/",
        }

        # ✅ Render the email template
        html_message = render_to_string('Following/following.html', context)
        plain_message = strip_tags(html_message)

        # ✅ Send the email
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
