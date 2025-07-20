from django.urls import path
from .views import ProfileDetailsView,UserPostDeleteView, userPostsView,EditProfileView,UserSearchView

urlpatterns = [
    path('details/', ProfileDetailsView.as_view(),name='profile_details'),
    path('posts/', userPostsView.as_view(), name='user_posts'),
    path('deletePost/', UserPostDeleteView.as_view(), name='user_post_delete'),
    path('edit/', EditProfileView.as_view(), name='edit_profile'),
    path('UserSearch/', UserSearchView.as_view(), name='user_search'),
]   