import logging
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated, AllowAny
from user.authentication import CookieJWTAuthentication

# Set up logger
logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class CookieTokenRefreshView(APIView):
    authentication_classes = [AllowAny]
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get("refresh")
        if not raw_refresh:
            logger.warning("Refresh token missing in cookies")
            return Response({"error": "Refresh token missing"}, status=401)

        try:
            refresh = RefreshToken(raw_refresh)   # Convert string to RefreshToken
            user = refresh.user

            logger.info(f"Refreshing tokens for user: {user.username}")

            # Create new access
            new_access = str(refresh.access_token)

            # Blacklist old refresh (if enabled)
            if getattr(refresh, "blacklist", None):
                try:
                    refresh.blacklist()
                    logger.info(f"Blacklisted old refresh token for user: {user.username}")
                except Exception as blacklist_error:
                    logger.error(f"Failed to blacklist refresh token: {blacklist_error}")

            # Issue new refresh
            new_refresh = RefreshToken.for_user(user)

            response = Response({"message": "Tokens refreshed successfully"}, status=200)
            response.set_cookie("access", new_access, httponly=True, secure=True, samesite="None", max_age=15*60)
            response.set_cookie("refresh", str(new_refresh), httponly=True, secure=True, samesite="None", max_age=7*24*60*60)

            logger.debug("New access and refresh tokens set in cookies")
            return response

        except Exception as e:
            logger.error(f"Refresh token error: {str(e)}", exc_info=True)
            return Response({"error": "Invalid or expired refresh token"}, status=401)


class MeApiView(APIView):
    """
    Returns authenticated user's info.
    Requires a valid access token in HttpOnly cookie.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        logger.info(f"User data requested: {user.username}")
        return Response({
            "username": user.username,
        }, status=status.HTTP_200_OK)
