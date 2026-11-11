import os
import secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.getenv('WELLIFY_DEBUG', 'False').lower() == 'true'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY when DEBUG=False.')
    SECRET_KEY = secrets.token_urlsafe(64)
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('replace-', 'development-'))):
    raise ImproperlyConfigured('Production requires a unique DJANGO_SECRET_KEY of at least 50 characters.')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'corsheaders', 'rest_framework', 'wellness', 'allauth', 'allauth.account', 'allauth.socialaccount',
    'allauth.socialaccount.providers.google', 'allauth.socialaccount.providers.apple',
    'allauth.socialaccount.providers.microsoft',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'corsheaders.middleware.CorsMiddleware',
    'wellness.middleware.SecurityPolicyMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware', 'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                          'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
if os.getenv('POSTGRES_DB'):
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['POSTGRES_DB'], 'USER': os.getenv('POSTGRES_USER', 'wellify'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''), 'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'), 'CONN_MAX_AGE': 60}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': os.getenv('WELLIFY_SQLITE_PATH', str(BASE_DIR / 'db.sqlite3')), 'OPTIONS': {'timeout': 20}}}
AUTH_USER_MODEL = 'wellness.User'
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Juba'
USE_I18N = True
USE_TZ = True
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
REST_FRAMEWORK = {
    'NUM_PROXIES': 0,
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.AnonRateThrottle', 'rest_framework.throttling.UserRateThrottle'],
    'DEFAULT_THROTTLE_RATES': {'anon': '60/hour', 'user': '600/hour', 'auth': '10/minute'},
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser', 'rest_framework.parsers.FormParser', 'rest_framework.parsers.MultiPartParser'],
}
CORS_ALLOWED_ORIGINS = os.getenv('FRONTEND_ORIGINS', 'https://localhost:5173,https://127.0.0.1:5173').split(',')
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 12
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
PASSWORD_RESET_TIMEOUT = 1800
DATA_UPLOAD_MAX_MEMORY_SIZE = 262144
FILE_UPLOAD_MAX_MEMORY_SIZE = 0
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = not DEBUG
if os.getenv('WELLIFY_TRUST_PROXY', 'False').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
STELLAR_HORIZON_URL = 'https://horizon-testnet.stellar.org'
HRW_ISSUER_PUBLIC_KEY = os.getenv('HRW_ISSUER_PUBLIC_KEY', '')
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend', 'allauth.account.auth_backends.AuthenticationBackend',
]
WELLIFY_FRONTEND_URL = os.getenv('WELLIFY_FRONTEND_URL', 'https://127.0.0.1:5173').rstrip('/')
if not DEBUG and any(not origin.startswith('https://') for origin in [WELLIFY_FRONTEND_URL, *CORS_ALLOWED_ORIGINS]):
    raise ImproperlyConfigured('Production frontend and CORS origins must use HTTPS.')
CACHES = {'default': {
    'BACKEND': os.getenv('WELLIFY_CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
    'LOCATION': os.getenv('WELLIFY_CACHE_LOCATION', 'wellify-security'),
}}
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@localhost')
LOGIN_REDIRECT_URL = WELLIFY_FRONTEND_URL + '/'
ACCOUNT_ADAPTER = 'wellness.social_auth.AccountAdapter'
SOCIALACCOUNT_ADAPTER = 'wellness.social_auth.SocialAccountAdapter'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_PROVIDERS = {
    'google': {'SCOPE': ['profile', 'email'], 'OAUTH_PKCE_ENABLED': True}, 'apple': {}, 'microsoft': {},
}
for provider in ('google', 'microsoft'):
    prefix = provider.upper()
    client_id = os.getenv(prefix + '_CLIENT_ID', '')
    client_secret = os.getenv(prefix + '_CLIENT_SECRET', '')
    if client_id and client_secret:
        SOCIALACCOUNT_PROVIDERS[provider]['APPS'] = [{'client_id': client_id, 'secret': client_secret}]
if all(os.getenv(name) for name in ('APPLE_CLIENT_ID', 'APPLE_KEY_ID', 'APPLE_TEAM_ID', 'APPLE_PRIVATE_KEY')):
    SOCIALACCOUNT_PROVIDERS['apple']['APPS'] = [{
        'client_id': os.environ['APPLE_CLIENT_ID'], 'secret': os.environ['APPLE_KEY_ID'],
        'key': os.environ['APPLE_TEAM_ID'],
        'settings': {'certificate_key': os.environ['APPLE_PRIVATE_KEY'].replace('\\n', '\n')},
    }]
