from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction
from django.utils.timezone import now
import logging

logger = logging.getLogger(__name__)

@method_decorator(never_cache, name="dispatch")
class ExpiredCleanupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        details = {}

        # Purge only expired cache rows for DatabaseCache (safe direct SQL) [web:192]
        try:
            conf = settings.CACHES.get("default", {})
            if conf.get("BACKEND") == "django.core.cache.backends.db.DatabaseCache":
                table = conf["LOCATION"]
                # Defensive quoting avoided as LOCATION is expected to be a table name config
                with connections["default"].cursor() as cursor, transaction.atomic():
                    cursor.execute(f"DELETE FROM {table} WHERE expires < %s", [now()])
                    details["cache_deleted"] = cursor.rowcount
            else:
                details["cache_status"] = "Non-DB cache; backend TTL handles expiry"
        except Exception as e:
            logger.error("Cache purge failed: %s", e, exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Flush expired SimpleJWT tokens via management command (recommended) [web:200]
        try:
            call_command("flushexpiredtokens")
            details["jwt_status"] = "flushexpiredtokens executed"
        except Exception as e:
            logger.error("flushexpiredtokens failed: %s", e, exc_info=True)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"detail": details}, status=status.HTTP_200_OK)
