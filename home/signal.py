import urllib.parse
from django.db.models.signals import post_save
from django.dispatch import receiver
from home.models import QuePdf
from home.tasks import send_email_task  # Import Celery task

@receiver(post_save, sender=QuePdf)
def que_pdf_notification(sender, instance, created, **kwargs):
    if created:
        # ✅ Prepare instance data
        instance_data = {
            "id": instance.id,
            "course": str(instance.course),
            "sub": str(instance.sub),
            "sem": str(instance.sem) if instance.sem else "N/A",
            "year": str(instance.year) if instance.year else "N/A",
            "div": str(instance.div) if instance.div else "N/A",
            "pdf_link": f"https://pixelclass.netlify.app/ns?sub={urllib.parse.quote(str(instance.sub))}&id={instance.id}&course={urllib.parse.quote(str(instance.course))}&choose=Assignment"
        }

        # ✅ Call Celery task asynchronously
        send_email_task.delay(instance.id, instance_data)
