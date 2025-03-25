from django.contrib import admin
from .models import PasswordResetToken , OTP
# Register your models here.

# Registering the model PasswordResetToken
@admin.register(PasswordResetToken)
class PasswordResetToken(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'is_reset', 'expiry_date', 'is_expired')


# Registering the model OTP
@admin.register(OTP)
class OTP(admin.ModelAdmin):
    list_display = ('user', 'otp', 'created_at', 'is_expired')