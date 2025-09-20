from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed

class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        # Fast local binding for headers/cookies access
        cookies = request.COOKIES

        # Prefer cookie token (logic preserved)
        raw_token = cookies.get('access')
        if raw_token is None:
            return None  # no token found; fall through to other authenticators

        # Validate token
        try:
            validated_token = self.get_validated_token(raw_token)
        except Exception as exc:
            # Keep message concise to avoid leaking internals
            raise AuthenticationFailed('Token Validation Error: {}'.format(exc))

        # Resolve user from token
        try:
            user = self.get_user(validated_token)
        except Exception as exc:
            raise AuthenticationFailed('User Retrieval Error: {}'.format(exc))

        return (user, validated_token)
