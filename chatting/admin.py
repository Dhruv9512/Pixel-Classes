from django.contrib import admin
from .models import Message
# Register your models here.
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'content', 'timestamp','is_seen','seen_at')
    search_fields = ('sender__username', 'receiver__username', 'content')
    list_filter = ('timestamp',)