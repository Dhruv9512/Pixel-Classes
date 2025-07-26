from django.db import models
from django.contrib.auth.models import User



# Create your models here.
class profile(models.Model):
    id = models.AutoField(primary_key=True)
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_pic = models.CharField(max_length=255, default="https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")
    course = models.CharField(max_length=30, default="B.C.A")

    def __str__(self):
        return self.user_obj.username
    

class Follow(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    following = models.ManyToManyField('self', symmetrical=False, related_name='followers')  

    