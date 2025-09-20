from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from Profile.serializers import (
    CombinedProfileSerializer, UserPostsSerializer, ProfileUpdateSerializer, UserSearchSerializer
)
from Profile.models import profile as ProfileModel
from django.contrib.auth.models import User
from urllib.parse import unquote, urlparse
from home.models import AnsPdf, QuePdf
from home.serializers import QuePdfSerializer
from vercel_blob import delete as del_, put
from user.authentication import CookieJWTAuthentication
from user.utils import user_key
from .models import Follow
from django.core.cache import cache
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator

class ProfileDetailsView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            username = request.data.get('username')
            if username:
                user = User.objects.only('id', 'username').filter(username=username).first()
                if not user:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                user = request.user

            # select_related for FK (user_obj) to avoid extra query in serializer [web:136][web:138]
            profile_obj = (
                ProfileModel.objects
                .select_related('user_obj')
                .only('id', 'user_obj__id', 'user_obj__username', 'user_obj__email', 'user_obj__date_joined', 'profile_pic', 'course')
                .filter(user_obj=user)
                .first()
            )
            if not profile_obj:
                return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = CombinedProfileSerializer(profile_obj)

            follow_obj = Follow.objects.only('id').filter(user=user).first()
            if follow_obj:
                follower_count = follow_obj.followers.count()
                following_count = follow_obj.following.count()
            else:
                follower_count = 0
                following_count = 0

            data = serializer.data
            data['follower_count'] = follower_count
            data['following_count'] = following_count
            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class userPostsView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            username = request.data.get('username')
            if username:
                user = User.objects.only('id', 'username').filter(username=username).first()
                if not user:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                user = request.user
                username = user.username

            # Join in que_pdf to remove N+1 when accessing its fields [web:136]
            posts = AnsPdf.objects.filter(name=username).select_related('que_pdf')
            serializer = UserPostsSerializer(posts, many=True)

            # Also include notes/other PDFs from QuePdf
            notes = QuePdf.objects.filter(username=username)
            qserializer_notes = QuePdfSerializer(notes, many=True)

            all_posts = []
            sdata = serializer.data
            for i, v in enumerate(posts):
                base = {
                    "name": getattr(v.que_pdf, "name", None),
                    "sub": getattr(v.que_pdf, "sub", None),
                    "choose": getattr(v.que_pdf, "choose", None),
                    "sem": getattr(v.que_pdf, "sem", None),
                }
                row = dict(sdata[i])
                row.update(base)
                all_posts.append(row)

            all_posts.extend(qserializer_notes.data)
            return Response({"posts": all_posts}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name="dispatch")
class UserPostDeleteView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        try:
            pdf_url = request.data.get('pdf_url')
            if not pdf_url:
                return Response({"error": "PDF URL is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Try both models with minimal fields [web:27]
            post = AnsPdf.objects.only('id', 'pdf').filter(pdf=pdf_url).first()
            if post is None:
                post = QuePdf.objects.only('id', 'pdf').filter(pdf=pdf_url).first()

            if not post:
                return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

            parsed_url = urlparse(pdf_url)
            blob_path = unquote(parsed_url.path.lstrip('/'))
            del_(blob_path)

            post.delete()

            user = request.user
            cache.delete(user_key(user))
            return Response({"message": "Post and blob deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name="dispatch")
class EditProfileView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            new_username = request.data.get('new_username')
            profile_pic = request.FILES.get('profile_pic')
            first_name = request.data.get('first_name')
            last_name = request.data.get('last_name')

            user = request.user
            username = user.username

            profile_obj = ProfileModel.objects.select_related('user_obj').filter(user_obj=user).first()
            if not profile_obj:
                return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

            changed = False
            if first_name:
                user.first_name = first_name
                changed = True
            if last_name:
                user.last_name = last_name
                changed = True

            if new_username and new_username != username:
                if User.objects.filter(username=new_username).exclude(id=user.id).only('id').exists():
                    return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
                # Bulk update related posts (same behavior, faster) [web:27]
                AnsPdf.objects.filter(name=username).update(name=new_username)
                user.username = new_username
                changed = True

            if changed:
                user.save(update_fields=["first_name", "last_name", "username"] if new_username else ["first_name", "last_name"])

            if profile_pic:
                old_profile_pic_url = profile_obj.profile_pic
                blob = put(f"Profile/{profile_pic}", profile_pic.read())
                new_profile_url = blob["url"]

                serializer = ProfileUpdateSerializer(profile_obj, data={'profile_pic': new_profile_url}, partial=True)
                if serializer.is_valid():
                    if old_profile_pic_url != "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp":
                        parsed_url = urlparse(old_profile_pic_url)
                        blob_path = unquote(parsed_url.path.lstrip('/'))
                        del_(blob_path)
                    serializer.save()
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            cache.delete(user_key(user))

            return Response({
                "message": "Profile updated successfully",
                "new_username": user.username,
                "profile_pic_url": profile_obj.profile_pic if profile_obj.profile_pic else None
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name="dispatch")
class UserSearchView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Limit columns for list view; serializer can still access these fields [web:27]
            users = User.objects.only('id', 'username', 'first_name', 'last_name', 'email', 'date_joined')
            serializer = UserSearchSerializer(users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name="dispatch")
class FollowView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            follow_username = request.data.get('follow_username')
            if not follow_username:
                return Response({"error": "follow_username is required"}, status=status.HTTP_400_BAD_REQUEST)

            follow_user = User.objects.only('id', 'username').filter(username=follow_username).first()
            if not follow_user:
                return Response({"error": "One or both users not found"}, status=status.HTTP_404_NOT_FOUND)

            user_follow_obj, _ = Follow.objects.get_or_create(user=user)
            follow_user_obj, _ = Follow.objects.get_or_create(user=follow_user)

            user_follow_obj.following.add(follow_user_obj)

            cache.delete(user_key(user))
            cache.delete(user_key(follow_user))
            return Response({"message": f"{user.username} is now following {follow_username}"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(never_cache, name="dispatch")
class UnfollowView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            user = request.user
            unfollow_username = request.data.get('unfollow_username')
            if not unfollow_username:
                return Response({"error": "unfollow_username is required"}, status=status.HTTP_400_BAD_REQUEST)

            unfollow_user = User.objects.only('id', 'username').filter(username=unfollow_username).first()
            if not unfollow_user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            follow_instance = Follow.objects.filter(user=user).first()
            unfollow_follow_instance = Follow.objects.filter(user=unfollow_user).first()
            if not follow_instance or not unfollow_follow_instance:
                return Response({"error": "Follow record not found"}, status=status.HTTP_404_NOT_FOUND)

            follow_instance.following.remove(unfollow_follow_instance)

            cache.delete(user_key(user))
            cache.delete(user_key(unfollow_user))
            return Response({"message": f"Unfollowed {unfollow_username}"}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FollowersView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            username = request.data.get('username')
            if username:
                user = User.objects.only('id', 'username').filter(username=username).first()
                if not user:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                user = request.user

            follow_obj = Follow.objects.filter(user=user).first()
            if not follow_obj:
                return Response({"error": "Follow object not found"}, status=status.HTTP_404_NOT_FOUND)

            # M2M/reverse: use select_related on the FK in the through model to include related User efficiently [web:136]
            followers = follow_obj.followers.select_related('user').all()
            followers_users = [f.user for f in followers]
            serializer = UserSearchSerializer(followers_users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FollowingView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            username = request.data.get('username')
            if username:
                user = User.objects.only('id', 'username').filter(username=username).first()
                if not user:
                    return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            else:
                user = request.user

            follow_obj = Follow.objects.filter(user=user).first()
            if not follow_obj:
                return Response({"error": "Follow object not found"}, status=status.HTTP_404_NOT_FOUND)

            following = follow_obj.following.select_related('user').all()
            following_users = [f.user for f in following]
            serializer = UserSearchSerializer(following_users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
