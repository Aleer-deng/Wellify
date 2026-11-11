from unittest.mock import patch
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient
from .models import Goal, Notification, Subscription
from .services import account_for
from .social_auth import SocialAccountAdapter

User = get_user_model()


class SocialAuthTests(TestCase):
    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.request = RequestFactory().get('/')

    def social_login(self, email='new@example.com'):
        return SocialLogin(user=User(email=email), account=SocialAccount(provider='google', uid='provider-123'))

    @override_settings(SOCIALACCOUNT_PROVIDERS={})
    def test_provider_list_is_public_and_never_contains_secrets(self):
        response = APIClient().get('/api/v1/auth/providers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['providers'], [
            {'id': key, 'name': name, 'enabled': False}
            for key, name in [('google', 'Google'), ('apple', 'Apple'), ('microsoft', 'Microsoft')]
        ])

    @override_settings(SOCIALACCOUNT_PROVIDERS={'google': {'APPS': [{'client_id': 'public-id', 'secret': 'private-secret'}]}})
    def test_only_configured_provider_is_available(self):
        response = APIClient().get('/api/v1/auth/providers/')
        self.assertTrue(response.data['providers'][0]['enabled'])
        self.assertFalse(response.data['providers'][1]['enabled'])
        self.assertNotIn('private-secret', response.content.decode())

    def test_social_login_requires_csrf_to_start(self):
        response = APIClient(enforce_csrf_checks=True).post('/api/v1/auth/social/google/login/')
        self.assertEqual(response.status_code, 403)

    @override_settings(SOCIALACCOUNT_PROVIDERS={'google': {
        'APPS': [{'client_id': 'test-client', 'secret': 'test-secret'}],
        'SCOPE': ['profile', 'email'], 'OAUTH_PKCE_ENABLED': True,
    }})
    def test_google_start_creates_state_and_pkce_without_contacting_provider(self):
        from urllib.parse import parse_qs, urlparse
        client = APIClient(enforce_csrf_checks=True)
        token = client.get('/api/v1/auth/csrf/').data['csrfToken']
        response = client.post('/api/v1/auth/social/google/login/', {'csrfmiddlewaretoken': token})
        self.assertEqual(response.status_code, 302)
        url = urlparse(response.url)
        self.assertEqual(url.hostname, 'accounts.google.com')
        query = parse_qs(url.query)
        self.assertTrue(query['state'][0])
        self.assertTrue(query['code_challenge'][0])
        self.assertEqual(query['client_id'], ['test-client'])

    def test_email_is_normalized(self):
        social = self.social_login(' New@Example.COM ')
        self.adapter.pre_social_login(self.request, social)
        self.assertEqual(social.user.email, 'new@example.com')

    def test_existing_email_is_never_automatically_linked(self):
        User.objects.create_user(username='existing', email='new@example.com', password='test-only')
        with self.assertRaises(ImmediateHttpResponse) as caught:
            self.adapter.pre_social_login(self.request, self.social_login('NEW@example.com'))
        self.assertIn('auth_error=existing_account', caught.exception.response.url)
        self.assertEqual(SocialAccount.objects.count(), 0)

    def test_missing_email_is_rejected(self):
        with self.assertRaises(ImmediateHttpResponse) as caught:
            self.adapter.pre_social_login(self.request, self.social_login(''))
        self.assertIn('auth_error=email_required', caught.exception.response.url)

    def test_inactive_social_account_is_rejected(self):
        user = User.objects.create_user(username='inactive', email='inactive@example.com', is_active=False)
        account = SocialAccount.objects.create(user=user, provider='google', uid='inactive-id')
        with self.assertRaises(ImmediateHttpResponse) as caught:
            self.adapter.pre_social_login(self.request, SocialLogin(user=user, account=account))
        self.assertIn('auth_error=inactive', caught.exception.response.url)

    def test_new_social_user_gets_goals_subscription_and_zero_points(self):
        user = User.objects.create_user(username='social', email='new@example.com')
        with patch('allauth.socialaccount.adapter.DefaultSocialAccountAdapter.save_user', return_value=user):
            self.assertEqual(self.adapter.save_user(self.request, self.social_login()), user)
        self.assertEqual(account_for(user).balance, 0)
        self.assertEqual(Goal.objects.filter(user=user).count(), 2)
        self.assertTrue(Subscription.objects.filter(user=user).exists())
        self.assertTrue(Notification.objects.filter(user=user, title='Welcome to Wellify').exists())

    def test_cancelled_provider_returns_to_frontend(self):
        with self.assertRaises(ImmediateHttpResponse) as caught:
            self.adapter.on_authentication_error(self.request, 'google', error='cancelled')
        self.assertIn('auth_error=provider_failed', caught.exception.response.url)
