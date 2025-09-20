from django.contrib import admin
from .models import Message

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'content', 'timestamp', 'is_seen', 'seen_at')
    search_fields = ('sender__username', 'receiver__username', 'content')
    list_filter = ('is_seen', 'timestamp')  # add is_seen for quick triage
    list_select_related = ('sender', 'receiver')  # avoid N+1 for FK columns [web:232]
    list_per_page = 50  # snappier pagination on large chat logs [web:172]
