from allauth.socialaccount.adapter import get_adapter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class SocialProvidersView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        configured = {app.provider for app in get_adapter().list_apps(request._request)}
        return Response({'providers': [
            {'id': key, 'name': name, 'enabled': key in configured}
            for key, name in [('google', 'Google'), ('apple', 'Apple'), ('microsoft', 'Microsoft')]
        ]})
