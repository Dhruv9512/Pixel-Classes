from django.contrib import admin
from .models import PasswordResetToken
# Register your models here.
@admin.register(PasswordResetToken)
class PasswordResetToken(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'is_reset', 'expiry_date', 'is_expired')
    