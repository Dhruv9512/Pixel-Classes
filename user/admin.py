from django.contrib import admin
from .models import PasswordResetToken , QuePdf
# Register your models here.

# Registering the model PasswordResetToken
@admin.register(PasswordResetToken)
class PasswordResetToken(admin.ModelAdmin):
    list_display = ('user', 'is_verified', 'is_reset', 'expiry_date', 'is_expired')

# Registering the model QuePdf Admin
@admin.register(QuePdf)
class QuePdfAdmin(admin.ModelAdmin):
    list_display = ('id','course','pdf','sem')
    