from django.db import models

class DatabaseCache(models.Model):
    cache_key = models.CharField(max_length=255, primary_key=True)
    value = models.TextField()
    expires = models.DateTimeField()  # <-- rename from 'expire' to 'expires'

    class Meta:
        db_table = 'my_cache_table'  # same as created by createcachetable
        managed = False  # Django won't create/drop this table
        verbose_name = "Database Cache"
        verbose_name_plural = "Database Caches"

    def __str__(self):
        return self.cache_key
