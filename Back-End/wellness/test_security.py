from datetime import datetime, timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from .models import Notification, Reward
from .services import account_for, issue_points

User = get_user_model()
PASSWORD = 'Security-Regression-78!'


class SecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('security', 'security@example.com', PASSWORD)
        self.other = User.objects.create_user('other-security', 'other-security@example.com', PASSWORD)
        self.api = APIClient(enforce_csrf_checks=True)
        self.api.force_login(self.user)

    def csrf(self):
        token = self.api.get('/api/v1/auth/csrf/').data['csrfToken']
        self.api.credentials(HTTP_X_CSRFTOKEN=token)

    @override_settings(SECURE_SSL_REDIRECT=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_https_redirect_and_secure_cookies(self):
        self.assertEqual(Client().get('/api/v1/status/').status_code, 301)
        client = APIClient()
        client.get('/api/v1/auth/csrf/', secure=True)
        self.assertTrue(client.cookies['csrftoken']['secure'])
        self.assertTrue(client.cookies['csrftoken']['httponly'])
        client.post('/api/v1/auth/login/', {'email': self.user.email, 'password': PASSWORD}, format='json', secure=True)
        self.assertTrue(client.cookies['sessionid']['secure'])
        self.assertTrue(client.cookies['sessionid']['httponly'])

    def test_headers_and_no_cache(self):
        response = self.api.get('/api/v1/profile/')
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('no-store', response['Cache-Control'])

    def test_upload_and_oversize_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertEqual(self.api.post('/api/v1/profile/', {'file': SimpleUploadedFile('evil.html', b'<script>1</script>')}, format='multipart').status_code, 415)
        self.assertEqual(self.api.post('/api/v1/auth/login/', {}, format='json', CONTENT_LENGTH='262145').status_code, 413)

    def test_other_users_notification_cannot_be_read_or_changed(self):
        notification = Notification.objects.create(user=self.other, title='Private', body='Private')
        self.csrf()
        path = f'/api/v1/notifications/{notification.pk}/'
        self.assertEqual(self.api.get(path).status_code, 404)
        self.assertEqual(self.api.patch(path, {'read': True}, format='json').status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.read)

    def test_price_and_user_are_authoritative(self):
        reward = Reward.objects.create(name='Server price', points_cost=50, stock=1)
        issue_points(self.user, 100, 'security-test', 'Test credit')
        self.csrf()
        response = self.api.post('/api/v1/rewards/redeem/', {
            'reward_id': reward.pk, 'idempotency_key': str(uuid.uuid4()),
            'points_cost': 1, 'user_id': self.other.pk,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['points_cost'], 50)
        self.assertEqual(response.data['user_id'], self.user.pk)
        self.assertEqual(account_for(self.user).balance, 50)

    def test_sql_payload_does_not_authenticate(self):
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get('/api/v1/auth/csrf/').data['csrfToken']
        response = client.post('/api/v1/auth/login/', {'email': "' OR 1=1 --", 'password': PASSWORD}, format='json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 2)

    def test_authenticated_write_requires_csrf(self):
        self.assertEqual(self.api.patch('/api/v1/profile/', {'name': 'Changed'}, format='json').status_code, 403)

    def test_admin_pages_and_api_require_staff(self):
        self.assertEqual(self.api.get('/admin/').status_code, 302)
        self.assertEqual(self.api.get('/api/v1/admin/users/').status_code, 403)
        self.assertEqual(self.api.get('/api/v1/admin/rewards/').status_code, 403)

    def test_admin_login_is_throttled(self):
        client = Client()
        for _ in range(10):
            client.post('/admin/login/', {})
        self.assertEqual(client.post('/admin/login/', {}).status_code, 429)

    def test_forwarded_ip_cannot_bypass_login_throttle(self):
        from .views import AuthThrottle
        client = APIClient(enforce_csrf_checks=True)
        csrf = client.get('/api/v1/auth/csrf/').data['csrfToken']
        with patch.object(AuthThrottle, 'get_rate', return_value='2/minute'):
            for index in range(2):
                result = client.post('/api/v1/auth/login/', {'email': 'missing@example.com', 'password': 'wrong'}, format='json', HTTP_X_CSRFTOKEN=csrf, HTTP_X_FORWARDED_FOR=f'10.0.0.{index}')
                self.assertEqual(result.status_code, 400)
            result = client.post('/api/v1/auth/login/', {'email': 'missing@example.com', 'password': 'wrong'}, format='json', HTTP_X_CSRFTOKEN=csrf, HTTP_X_FORWARDED_FOR='10.0.0.99')
            self.assertEqual(result.status_code, 429)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_reset_csrf_email_expiry_and_one_use(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/auth/password-reset/', {'email': self.user.email}).status_code, 403)
        client.get('/auth/password-reset/')
        csrf = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/auth/password-reset/', {'email': self.user.email, 'csrfmiddlewaretoken': csrf}).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/auth/reset/', mail.outbox[0].body)
        now = datetime.now()
        with patch.object(default_token_generator, '_now', return_value=now):
            token = default_token_generator.make_token(self.user)
        with patch.object(default_token_generator, '_now', return_value=now + timedelta(seconds=1801)):
            self.assertFalse(default_token_generator.check_token(self.user, token))
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = client.get(f'/auth/reset/{uid}/{token}/')
        self.assertEqual(response.status_code, 302)
        path = response.url
        client.get(path)
        csrf = client.cookies['csrftoken'].value
        bad = client.post(path, {'new_password1': '123', 'new_password2': '123', 'csrfmiddlewaretoken': csrf})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, 'too short')
        too_long = client.post(path, {'new_password1': 'Zx-89!' * 30, 'new_password2': 'Zx-89!' * 30, 'csrfmiddlewaretoken': csrf})
        self.assertEqual(too_long.status_code, 200)
        self.assertIn('new_password1', too_long.context['form'].errors)
        new_password = 'A-New-Secure-Password-85!'
        result = client.post(path, {'new_password1': new_password, 'new_password2': new_password, 'csrfmiddlewaretoken': csrf})
        self.assertEqual(result.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))
        self.assertFalse(default_token_generator.check_token(self.user, token))
