from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from Profile.serializers import CombinedProfileSerializer,UserPostsSerializer,ProfileUpdateSerializer, UserSearchSerializer
from Profile.models import profile as ProfileModel
from django.contrib.auth.models import User
from urllib.parse import unquote, urlparse
from home.models import AnsPdf
from vercel_blob import delete  as del_, put
from .models import Follow

class ProfileDetailsView(APIView):
    def post(self, request):
        try:
            # Get username from request
            username = request.data.get('username')
            if not username:
                return Response({"error": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Try to fetch the user
            user = User.objects.get(username=username)

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
    def post(self, request):
        try:
            username = request.data.get('username')
          
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
        

class UserPostDeleteView(APIView):
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

            return Response({"message": "Post and blob deleted successfully"}, status=status.HTTP_204_NO_CONTENT)

        except AnsPdf.DoesNotExist:
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class EditProfileView(APIView):
    def put(self, request):
        try:
            username = request.data.get('username')
            new_username = request.data.get('new_username')
            profile_pic = request.FILES.get('profile_pic') 

            if not username:
                return Response({"error": "Old username is required"}, status=status.HTTP_400_BAD_REQUEST)

            # Get user and profile
            user = User.objects.get(username=username)
            profile_obj = ProfileModel.objects.get(user_obj=user)


            # ✅ Update username if provided
            if User.objects.filter(username=new_username).exists():
                user.username = new_username
                user.save()
          

            # ✅ Update profile_pic if provided
            old_profile_pic_url = profile_obj.profile_pic 
            blob = put(f"Profile/{profile_pic}", profile_pic.read())
            profile_pic = blob["url"]
            serializer = ProfileUpdateSerializer(profile_obj, data={'profile_pic': profile_pic}, partial=True)
            if serializer.is_valid():
                parsed_url = urlparse(old_profile_pic_url)
                blob_path = unquote(parsed_url.path.lstrip('/'))
                del_(blob_path)
             
                profile_obj.profile_pic = profile_pic
                profile_obj.save()    
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # ✅ Return appropriate message
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
class UserSearchView(APIView):
    def get(self, request):
        try:
            users = User.objects.all()
            serializer = UserSearchSerializer(users, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# followe view
class FollowView(APIView):
    def post(self, request):
        try:
            username = request.data.get('username')
            follow_username = request.data.get('follow_username')

            if not username or not follow_username:
                return Response({"error": "Both usernames are required"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.get(username=username)
            follow_user = User.objects.get(username=follow_username)

            # Get or create Follow instance
            user_follow_obj, _ = Follow.objects.get_or_create(user=user)
            follow_user_obj, _ = Follow.objects.get_or_create(user=follow_user)

            user_follow_obj.following.add(follow_user_obj)

            return Response({"message": f"{username} is now following {follow_username}"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "One or both users not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
           
class UnfollowView(APIView):
    def post(self, request):
        try:
            username = request.data.get('username')
            unfollow_username = request.data.get('unfollow_username')

            if not username or not unfollow_username:
                return Response({"error": "Username and unfollow_username are required"}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects.get(username=username)
            unfollow_user = User.objects.get(username=unfollow_username)

            # Get Follow objects
            follow_instance = Follow.objects.get(user=user)
            unfollow_follow_instance = Follow.objects.get(user=unfollow_user)
        
            follow_instance.following.remove(unfollow_follow_instance)

            return Response({"message": f"Unfollowed {unfollow_username}"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Follow.DoesNotExist:
            return Response({"error": "Follow record not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class FollowersView(APIView):
    def post(self, request):
        try:
            username = request.data.get('username')
            user = User.objects.get(username=username)
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
    def post(self, request):
        try:
            username = request.data.get('username')
            user = User.objects.get(username=username)
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