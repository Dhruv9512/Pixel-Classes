import urllib.parse
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from home.models import profile

@shared_task
def send_email_task(instance_id, instance_data):
    from home.models import QuePdf  # Import inside the function to avoid circular imports

    try:
        instance = QuePdf.objects.get(id=instance_id)

        # ✅ Get all users with the matching course
        matching_users = profile.objects.filter(course=instance.course)
        if not matching_users.exists():
            print(f"⚠️ No users found for course: {instance.course}")
            return  

        # ✅ Send emails
        subject = "📄 New Que PDF Added!"
        for user in matching_users:
            try:
                context = {
                    'instance': instance_data,
                    'user': {'username': user.user_obj.username},
                    'pdf_link': instance_data["pdf_link"]
                }

                html_message = render_to_string('que_pdf_notification/que_pdf_notification.html', context)
                plain_message = strip_tags(html_message)

                send_mail(
                    subject,
                    plain_message,
                    settings.EMAIL_HOST_USER,
                    [user.user_obj.email],
                    html_message=html_message,
                    fail_silently=False
                )

                print(f"✅ Email sent to {user.user_obj.username} ({user.user_obj.email})")

            except Exception as e:
                print(f"❌ Failed to send email to {user.user_obj.username} ({user.user_obj.email}): {e}")

    except Exception as e:
        print(f"❌ Error fetching instance: {e}")
