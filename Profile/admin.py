from django.contrib import admin
from .models import profile,Follow


# Register your models here.
@admin.register(profile)
class profileAdmin(admin.ModelAdmin):
    list_display = ('id' , 'user_obj' , 'profile_pic')

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_following')

    def get_following(self, obj):
        return ", ".join([user.username for user in obj.following.all()])

    get_following.short_description = 'Following'
