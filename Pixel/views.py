import logging
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import IsAuthenticated, AllowAny
from user.authentication import CookieJWTAuthentication
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)

# small helper to set auth cookies consistently (SameSite=None + Secure + HttpOnly) [web:6]
def _set_auth_cookies(response, access_token, refresh_token, access_max_age=30*60, refresh_max_age=7*24*60*60):
    response.set_cookie(
        key="access",
        value=str(access_token),
        httponly=True,
        secure=True,
        samesite="None",
        max_age=access_max_age,
    )
    response.set_cookie(
        key="refresh",
        value=str(refresh_token),
        httponly=True,
        secure=True,
        samesite="None",
        max_age=refresh_max_age,
    )
    return response

@method_decorator(never_cache, name="dispatch")
class CookieTokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get("refresh")
        if not raw_refresh:
            logger.warning("Refresh token missing in cookies")
            return Response({"error": "Refresh token missing"}, status=401)

        try:
            refresh = RefreshToken(raw_refresh)

            # Read user_id directly from token claims without extra parsing work (same as before)
            user_id = refresh.get("user_id")
            User = get_user_model()
            # Fetch only id/username to reduce overhead while logging [web:172]
            user = User.objects.only("id", "username").get(id=user_id)

            logger.info(f"Refreshing tokens for user: {user.username}")

            new_access = str(refresh.access_token)

            # Blacklist old refresh (optional, unchanged)
            try:
                refresh.blacklist()
                logger.info(f"Blacklisted old refresh token for {user.username}")
            except Exception:
                logger.debug("Token blacklist not configured")

            # Issue new refresh
            new_refresh = RefreshToken.for_user(user)

            response = Response({"message": "Tokens refreshed successfully"}, status=200)
            _set_auth_cookies(response, new_access, str(new_refresh))  # central cookie setter [web:6]
            return response

        except Exception as e:
            logger.error(f"Refresh token error: {e}", exc_info=True)
            return Response({"error": "Invalid or expired refresh token"}, status=401)

@method_decorator(never_cache, name="dispatch")
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
        return Response({"username": user.username}, status=status.HTTP_200_OK)

@method_decorator(never_cache, name="dispatch")
class GetWsTokenView(APIView):
    """
    Returns a short-lived WebSocket token for the authenticated user.
    Requires a valid access token in HttpOnly cookie.
    """
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            if not user:
                logger.warning("Unauthorized attempt to get WebSocket token")
                return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

            # Create refresh token for user with 2-min lifetime (unchanged semantics)
            refresh = RefreshToken.for_user(user)
            refresh.set_exp(lifetime=timedelta(minutes=2))

            # Create access token with 2-min lifetime
            access = refresh.access_token
            access.set_exp(lifetime=timedelta(minutes=2))

            ws_token = str(access)

            logger.info(f"WebSocket token issued for user: {user.username}")
            return Response({"ws_token": ws_token}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error generating WebSocket token: {e}", exc_info=True)
            return Response({"error": "Failed to generate WebSocket token"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
