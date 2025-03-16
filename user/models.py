from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.timezone import now

# Create your models here.
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255)
    is_verified = models.BooleanField(default=False)
    is_reset = models.BooleanField(default=False)
    expiry_date = models.DateTimeField()
    created_at = models.DateTimeField(default=now) 

    def is_expired(self):
        return timezone.now() > self.expiry_date

    def __str__(self):
        return f"Token for {self.user.username} ({'Expired' if self.is_expired() else 'Active'})"
    