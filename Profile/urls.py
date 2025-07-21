from django.urls import path
from .views import ProfileDetailsView,UserPostDeleteView, userPostsView,EditProfileView,UserSearchView, FollowView, UnfollowView,FollowersView,FollowingView

urlpatterns = [
    path('details/', ProfileDetailsView.as_view(),name='profile_details'),
    path('posts/', userPostsView.as_view(), name='user_posts'),
    path('deletePost/', UserPostDeleteView.as_view(), name='user_post_delete'),
    path('edit/', EditProfileView.as_view(), name='edit_profile'),
    path('UserSearch/', UserSearchView.as_view(), name='user_search'),
    path('follow/', FollowView.as_view(), name='follow_user'),
    path('unfollow/', UnfollowView.as_view(), name='unfollow_user'),
    path('followers/', FollowersView.as_view(), name='followers'),
    path('following/', FollowingView.as_view(), name='following'),
]   