from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated
from user.authentication import CookieJWTAuthentication
from rest_framework_simplejwt.views import TokenRefreshView




@method_decorator(csrf_exempt, name='dispatch')
class CookieTokenRefreshView(TokenRefreshView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token missing"}, status=401)

        try:
            # Extract user before blacklisting
            user = refresh_token.user  

            # Generate new access token
            new_access = str(refresh_token.access_token)

            # Blacklist the old refresh token (if enabled)
            if getattr(refresh_token, "blacklist", None):
                refresh_token.blacklist()

            # Now create a completely new refresh token
            new_refresh = RefreshToken.for_user(user)


            response = Response({"message": "Tokens refreshed successfully"}, status=200)

            # Set cookies
            response.set_cookie("access", new_access, httponly=True, secure=True, samesite="None", max_age=15*60)
            response.set_cookie("refresh", str(new_refresh), httponly=True, secure=True, samesite="None", max_age=7*24*60*60)

            return response

        except Exception as e:
            print("Refresh token error:", e)  # debug log
            return Response({"error": "Invalid or expired refresh token"}, status=401)


class MeApiView(APIView):
    """
    Returns authenticated user's info.
    Requires a valid access token in HttpOnly cookie.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # At this point, IsAuthenticated ensures request.user is valid
        user = request.user
        return Response({
            "username": user.username,
        }, status=status.HTTP_200_OK)