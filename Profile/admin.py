from django.contrib import admin
from .models import profile,Follow


# Register your models here.
@admin.register(profile)
class profileAdmin(admin.ModelAdmin):
    list_display = ('id' , 'user_obj' , 'profile_pic')

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'following')