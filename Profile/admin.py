from django.contrib import admin
from django.db.models import Prefetch, Value
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User
from .models import profile, Follow

# Register your models here.
@admin.register(profile)
class profileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_obj', 'profile_pic')
    # Prefetch related user for faster changelist rendering if needed
    list_select_related = ('user_obj',)  # avoid extra queries when showing user_obj [web:27]
    search_fields = ('user_obj__username', 'user_obj__email')  # admin UX improvement without logic change [web:143]
    list_filter = ('course',)  # fast filtering on low-cardinality field [web:143]

@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_following')
    # Pull the related user in one query for the main row [web:27]
    list_select_related = ('user',)

    # Prefetch following->user to avoid N+1 on get_following for each row [web:27]
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related(
            Prefetch('following', queryset=Follow.objects.select_related('user').only('id', 'user__username'))
        )  # minimizes fields and joins [web:27]

    def get_following(self, obj):
        # Join usernames from the prefetched related set without extra queries [web:27]
        return ", ".join(f.user.username for f in obj.following.all())
    get_following.short_description = 'Following'

    search_fields = ('user__username', 'user__email')  # quick lookup by owner [web:143]
    # Optional filter by whether a user follows anyone, without changing logic
    # Uses the M2M to filter efficiently in admin [web:27]
    list_filter = ('following',)
