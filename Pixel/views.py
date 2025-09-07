from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

@method_decorator(csrf_exempt, name='dispatch')
class CookieTokenRefreshView(APIView):
    """
    Refresh access and refresh tokens and set them in HttpOnly cookies.
    Frontend does NOT need to handle tokens manually.
    """
    def post(self, request):
        try:
            # Get refresh token from cookie
            refresh_token = request.COOKIES.get('refresh')
            if not refresh_token:
                return Response({'error': 'Refresh token missing'}, status=status.HTTP_401_UNAUTHORIZED)

            # Validate and rotate refresh token
            refresh = RefreshToken(refresh_token)
            new_access = str(refresh.access_token)

            # Rotate refresh token if enabled
            if getattr(refresh, 'blacklist', None):
                refresh.blacklist()  # invalidate old refresh token if blacklisting

            new_refresh = str(refresh)  # new refresh token

            response = Response({
                "message": "Tokens refreshed successfully"
            }, status=status.HTTP_200_OK)

            # Set access token cookie (15 min)
            response.set_cookie(
                key='access',
                value=new_access,
                httponly=True,
                secure=True,
                samesite='None',
                max_age=15*60,
            )

            # Set refresh token cookie (7 days)
            response.set_cookie(
                key='refresh',
                value=new_refresh,
                httponly=True,
                secure=True,
                samesite='None',
                max_age=7*24*60*60,
            )

            return response

        except Exception as e:
            return Response({"error": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)



class MeView(APIView):
    """
    Returns authenticated user's info.
    Requires a valid access token in HttpOnly cookie.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # At this point, IsAuthenticated ensures request.user is valid
        user = request.user
        return Response({
            "username": user.username,
        }, status=status.HTTP_200_OK)