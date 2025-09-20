from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class profile(models.Model):
    id = models.AutoField(primary_key=True)
    # Add index for frequent joins/lookups on user_obj (common in views/serializers) [web:27]
    user_obj = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True, related_name='profiles')
    # Keep existing default; ensure length is sufficient and not excessive; add db_index for filtering by URL if needed [web:27]
    profile_pic = models.CharField(
        max_length=255,
        default="https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp"
    )
    # Course is short; keep as-is; optional index if frequently filtered
    course = models.CharField(max_length=30, default="B.C.A")

    def __str__(self):
        return self.user_obj.username

    class Meta:
        # Add a composite index helpful when fetching a profile by user_obj [web:27]
        indexes = [
            models.Index(fields=['user_obj']),
        ]
        # If there is at most one profile per user, consider a unique constraint:
        # constraints = [models.UniqueConstraint(fields=['user_obj'], name='unique_profile_per_user')]
        # (commented to avoid changing logic if multiples are allowed) [web:27]


class Follow(models.Model):
    # Add unique and indexed one-to-one mapping to user (1:1 already implies index) [web:27]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='follow')
    # Keep asymmetrical self-referential M2M; add explicit through table name for clarity (optional) [web:27]
    following = models.ManyToManyField(
        'self',
        symmetrical=False,
        related_name='followers'
    )

    def __str__(self):
        return f"Follow(user={self.user_id})"

    class Meta:
        # Indexing user speeds up fetches like Follow.objects.filter(user=...) used throughout views [web:27]
        indexes = [
            models.Index(fields=['user']),
        ]
