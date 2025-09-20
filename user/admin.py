from django.contrib import admin
from .models import PasswordResetToken

@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    # Same visible columns
    list_display = ('user', 'is_verified', 'is_reset', 'expiry_date', 'is_expired')

    # Join user in the base queryset to avoid extra queries per row [web:172]
    list_select_related = ('user',)

    # Useful sidebar filters that leverage indexed booleans/dates [web:163]
    list_filter = ('is_verified', 'is_reset', 'expiry_date')

    # Quick search by username or exact token; exact lookup is faster for tokens [web:167]
    search_fields = ('user__username', 'token__exact')

    # Optional: order by newest first for faster triage (no logic change)
    ordering = ('-created_at',)
