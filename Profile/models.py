from django.db import models
from django.contrib.auth.models import User



# Create your models here.
class profile(models.Model):  
    id = models.AutoField(primary_key=True)
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)  