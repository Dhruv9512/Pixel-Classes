from django.contrib import admin
from django.utils.html import format_html
from .models import DatabaseCache

@admin.register(DatabaseCache)
class DatabaseCacheAdmin(admin.ModelAdmin):
    list_display = ('cache_key', 'value_truncated', 'expires')
    search_fields = ('cache_key',)
    list_filter = ('expires',)  # quick filter by expiration date [web:191]
    list_per_page = 50  # lighter changelist pages on large tables [web:172]

    # Show a short preview to avoid rendering megabytes per row in list view [web:167]
    def value_truncated(self, obj):
        v = obj.value or ""
        if len(v) > 120:
            v = v[:120] + "…"
        # Avoid heavy formatting; plain text is fine here
        return v
    value_truncated.short_description = 'value'
