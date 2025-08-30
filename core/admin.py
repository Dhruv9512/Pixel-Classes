
# Register your models here.
from django.contrib import admin
from .models import DatabaseCache

@admin.register(DatabaseCache)
class DatabaseCacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'value', 'expires')
    search_fields = ('cache_key',)
