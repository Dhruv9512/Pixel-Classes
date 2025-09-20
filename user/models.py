from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.timezone import now

class PasswordResetToken(models.Model):
    # ForeignKey already creates an index; keep explicit Meta index for common filters. [web:27]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, db_index=True)  # tokens are looked up often; index speeds get() calls. [web:153]
    is_verified = models.BooleanField(default=False)
    is_reset = models.BooleanField(default=False)
    expiry_date = models.DateTimeField(db_index=True)  # accelerates expiry sweeps and range filters. [web:27][web:158]
    created_at = models.DateTimeField(default=now, db_index=True)  # helpful for ordering and “latest token” lookups. [web:27]

    def is_expired(self):
        return timezone.now() > self.expiry_date

    def __str__(self):
        return f"Token for {self.user.username} ({'Expired' if self.is_expired() else 'Active'})"

    class Meta:
        # Composite indexes match common access patterns in the views:
        # - fetch latest token per user
        # - validate specific token for a user
        indexes = [
            models.Index(fields=['user', 'created_at']),   # latest-by-user queries. [web:27]
            models.Index(fields=['user', 'token']),         # validation path: user + token. [web:27]
            models.Index(fields=['user', 'is_verified', 'is_reset', 'created_at']),  # status checks. [web:27]
        ]
    
