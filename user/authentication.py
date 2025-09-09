from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Look for token in cookies instead of headers
        raw_token = request.COOKIES.get('access')
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except Exception as e:
            return AuthenticationFailed(f'Token Validation Error: ' + str(e))

        try:
            user = self.get_user(validated_token)
            return user, validated_token
        except Exception as e:
            return AuthenticationFailed(f'User Retrieval Error: ' + str(e))