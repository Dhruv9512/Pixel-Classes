from django.db import models
from django.contrib.auth.models import User



# Create your models here.
class profile(models.Model):  # Renamed to `Profile` (capitalized for convention)
    id = models.AutoField(primary_key=True)
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.CharField(max_length=20)  