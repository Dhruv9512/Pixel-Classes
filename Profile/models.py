from django.db import models
from django.contrib.auth.models import User



# Create your models here.
class profile(models.Model):
    id = models.AutoField(primary_key=True)
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE)
    profile_pic = models.CharField(max_length=255, default="https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp")

    def __str__(self):
        return self.user_obj.username
    

# class Follow(models.Model):
#     follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_set')
#     following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='follower_set')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         unique_together = ('follower', 'following')  