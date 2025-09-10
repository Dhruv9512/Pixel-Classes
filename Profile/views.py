from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from Profile.serializers import CombinedProfileSerializer,UserPostsSerializer,ProfileUpdateSerializer, UserSearchSerializer
from Profile.models import profile as ProfileModel
from django.contrib.auth.models import User
from urllib.parse import unquote, urlparse
from home.models import AnsPdf
from vercel_blob import delete  as del_, put
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
            
            # Try to fetch the user
            username = request.data.get('username')
            user=User.objects.get(username=username)

            # Try to fetch the profile
            profile_obj = ProfileModel.objects.get(user_obj=user)

            # Use serializer to build response
            serializer = CombinedProfileSerializer(profile_obj)

            # Add follower/following count
            try:
                follow_obj = Follow.objects.get(user=user)
                follower_count = follow_obj.followers.count()
                following_count = follow_obj.following.count()
            except Follow.DoesNotExist:
                follower_count = 0
                following_count = 0

            data = serializer.data
            data['follower_count'] = follower_count
            data['following_count'] = following_count
            
            return Response(data, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        except ProfileModel.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class userPostsView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            user = request.user
            username = user.username
            # Fetch posts related to the user
            posts = AnsPdf.objects.filter(name=username)
            serializer = UserPostsSerializer(posts, many=True)

            all_posts = []

            for i,v in enumerate(posts):
                all_posts.append({
                    "name": v.que_pdf.name,
                    "sub": v.que_pdf.sub,
                    "choose": v.que_pdf.choose,
                    "sem": v.que_pdf.sem,
                })
                for key, value in serializer.data[i].items():
                    all_posts[i][key] = value

            return Response({
                "posts": all_posts,
            }, status=status.HTTP_200_OK)
        

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
@method_decorator(never_cache, name="dispatch")
class UserPostDeleteView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def delete(self, request):
        try:
            # Get PDF URL from request
            pdf_url = request.data.get('pdf_url')
            if not pdf_url:
                return Response({"error": "PDF URL is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch the post
            post = AnsPdf.objects.get(pdf=pdf_url)

            # Delete the blob from Vercel Blob first
            parsed_url = urlparse(pdf_url)
            blob_path = unquote(parsed_url.path.lstrip('/'))
            del_(blob_path)

            # Now delete the database post
            post.delete()

            user = request.user
            cache.delete(user_key(user))
            return Response({"message": "Post and blob deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

        except AnsPdf.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

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

           
            # Get user
            user = request.user
            username = user.username
            profile_obj = ProfileModel.objects.get(user_obj=user)

            # ✅ Update first and last name
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name

            # ✅ Update username
            if new_username and new_username != username:
                if User.objects.filter(username__iexact=new_username).exclude(id=user.id).exists():
                    return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

                # Update AnsPdf records where name matches (case-insensitive)
                posts = AnsPdf.objects.filter(name=username)
                for post in posts:
                    post.name = new_username
                    post.save()

                user.username = new_username

            # Save user if anything changed
            user.save()

            # ✅ Update profile pic
            if profile_pic:
                old_profile_pic_url = profile_obj.profile_pic
                blob = put(f"Profile/{profile_pic}", profile_pic.read())
                new_profile_url = blob["url"]

                serializer = ProfileUpdateSerializer(profile_obj, data={'profile_pic': new_profile_url}, partial=True)
                if serializer.is_valid():

                    if old_profile_pic_url != "https://mphkxojdifbgafp1.public.blob.vercel-storage.com/Profile/p.webp":
                        # Delete old profile pic from storage
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

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except ProfileModel.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# create a user search view
@method_decorator(never_cache, name="dispatch")
class UserSearchView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):
        try:
            users = User.objects.all()
            serializer = UserSearchSerializer(users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# followe view
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

            
            follow_user = User.objects.get(username=follow_username)

            # Get or create Follow instance
            user_follow_obj, _ = Follow.objects.get_or_create(user=user)
            follow_user_obj, _ = Follow.objects.get_or_create(user=follow_user)

            user_follow_obj.following.add(follow_user_obj)

            cache.delete(user_key(user))
            cache.delete(user_key(follow_user))
            return Response({"message": f"{user.username} is now following {follow_username}"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "One or both users not found"}, status=status.HTTP_404_NOT_FOUND)
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

            unfollow_user = User.objects.get(username=unfollow_username)

            # Get Follow objects
            follow_instance = Follow.objects.get(user=user)
            unfollow_follow_instance = Follow.objects.get(user=unfollow_user)
        
            follow_instance.following.remove(unfollow_follow_instance)
            cache.delete(user_key(user))
            cache.delete(user_key(unfollow_user))
            return Response({"message": f"Unfollowed {unfollow_username}"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({"error": "Follow record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class FollowersView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            user=request.user
            follow_obj = Follow.objects.get(user=user)
            followers = follow_obj.followers.all()
            followers_users = [f.user for f in followers]
            serializer = UserSearchSerializer(followers_users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({"error": "Follow object not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class FollowingView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def post(self, request):
        try:
            user = request.user
            follow_obj = Follow.objects.get(user=user)
            following = follow_obj.following.all()
            following_users = [f.user for f in following]
            serializer = UserSearchSerializer(following_users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({"error": "Follow object not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)