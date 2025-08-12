import datetime
from django.db import models
from django.contrib.auth.models import User
import pytz


# Function to return the current time as a string in HH:MM:SS format
def get_current_datetime():
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist).strftime("%Y-%m-%d %I:%M %p")

class Message(models.Model):
    sender = models.ForeignKey(User, related_name='sent_messages', on_delete=models.CASCADE)
    receiver = models.ForeignKey(User, related_name='received_messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.CharField(max_length=30, default=get_current_datetime)

    
    is_seen = models.BooleanField(default=False) 
    seen_at = models.CharField(max_length=30, default=get_current_datetime)


    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.content}"
