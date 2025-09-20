from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
import pytz

# Function to return the current time as a string in HH:MM:SS format
def get_current_datetime():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime("%Y-%m-%d %I:%M %p")

class Message(models.Model):
    # FK joins are common; add related_name (kept) and db_index for faster filters [web:27]
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE, db_index=True)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE, db_index=True)

    content = models.TextField()

    # Keep string-based timestamp/seen_at (no logic change). Limit max_length to avoid oversized rows. [web:27]
    # Format "YYYY-MM-DD HH:MM AM/PM" fits within 20 chars; give headroom.
    timestamp = models.CharField(max_length=32, default=get_current_datetime, db_index=True)
    is_seen = models.BooleanField(default=False, db_index=True)
    seen_at = models.CharField(max_length=32, default=get_current_datetime)

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content}"

    class Meta:
        # Composite index to speed common inbox/outbox queries and ordered retrievals. [web:27]
        indexes = [
            models.Index(fields=['sender', 'receiver', 'timestamp']),
            models.Index(fields=['receiver', 'is_seen', 'timestamp']),
        ]
