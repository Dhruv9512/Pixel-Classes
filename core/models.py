from django.db import models

class DatabaseCache(models.Model):
    cache_key = models.CharField(max_length=255, primary_key=True)
    value = models.TextField()
    expires = models.DateTimeField()  # matches Django's db cache schema [web:38]

    class Meta:
        db_table = 'my_cache_table'   # must match your CACHES["default"]["LOCATION"] [web:38]
        managed = False               # do not create/alter; table managed by Django cache framework [web:38]
        verbose_name = "Database Cache"
        verbose_name_plural = "Database Caches"
        # Helpful indexes for admin/maintenance access patterns (no schema change if already present)
        indexes = [
            models.Index(fields=['expires']),     # speeds DELETE WHERE expires < now() cleanups [web:38]
            # Primary key already indexes cache_key; included here for clarity only.
        ]

    def __str__(self):
        return self.cache_key
