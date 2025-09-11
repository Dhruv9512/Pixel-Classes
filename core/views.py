from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from django.utils.decorators import method_decorator
from rest_framework import status
from user.authentication import CookieJWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
# Create your views here.



@method_decorator(never_cache, name="dispatch")
class ExpiredCleanupView(APIView):
    authentication_classes = [CookieJWTAuthentication]
    permission_classes = [IsAuthenticated]
    def get(self, request):

        try:
            from django.core.cache import cache
            cache.clear_expired()
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
             # ---------- 1. Cleanup expired outstanding tokens ----------
            expired_tokens = OutstandingToken.objects.filter(expires_at__lt=now())
            count_outstanding = expired_tokens.count()
            expired_tokens.delete()

            # ---------- 2. Cleanup expired blacklisted tokens ----------
            expired_blacklisted = BlacklistedToken.objects.filter(token__expires_at__lt=now())
            count_blacklisted = expired_blacklisted.count()
            expired_blacklisted.delete()
            return Response(
                {"detail": f"Deleted {count_outstanding} expired outstanding tokens and {count_blacklisted} expired blacklisted tokens and expired cache."},
                status=200
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        