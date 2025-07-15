from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from Profile.serializers import profileSerializer
from Profile.models import profile as ProfileModel
from django.contrib.auth.models import User

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
            try:
                profile_obj = ProfileModel.objects.get(user_obj=user)
                profile_pic_url = profile_obj.profile_pic.url 
            except ProfileModel.DoesNotExist:
                profile_pic_url = None

            # Construct response
            response = {
                'username': user.username,
                'email': user.email,
                'joined_date': user.date_joined,
                'profile_pic': profile_pic_url
            }
            return Response(response, status=status.HTTP_200_OK)
        
        except Exception as e:
            # Catch any unexpected errors
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

