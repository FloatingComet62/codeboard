from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import UserSerializer


def verify_google_credential(credential):
    """Verify a Google Identity Services ID token and return its claims, or None."""
    try:
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError:
        return None
    if not claims.get('email_verified'):
        return None
    allowed = settings.GOOGLE_ALLOWED_DOMAINS
    if allowed and claims.get('hd') not in allowed:
        return None
    return claims


class GoogleLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({'error': 'Google credential is required'}, status=status.HTTP_400_BAD_REQUEST)

        claims = verify_google_credential(credential)
        if not claims:
            return Response({'error': 'Invalid Google credential'}, status=status.HTTP_401_UNAUTHORIZED)

        profile = {
            'email': claims['email'],
            'first_name': claims.get('given_name', ''),
            'last_name': claims.get('family_name', ''),
            'picture': claims.get('picture', ''),
        }
        user = User.objects.filter(google_id=claims['sub']).first()
        if user is None:
            # Link by email so accounts created via createsuperuser can sign in with Google.
            user = User.objects.filter(email__iexact=claims['email']).first()
            if user is None:
                user = User.objects.create_user(**profile)
            user.google_id = claims['sub']
        for field, value in profile.items():
            setattr(user, field, value)
        user.save()

        if not user.is_active:
            return Response({'error': 'Account is disabled'}, status=status.HTTP_403_FORBIDDEN)

        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': UserSerializer(user).data}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.auth.delete()
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
