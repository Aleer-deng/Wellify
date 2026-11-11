"""Explicit HTTP settings for tests only; production remains HTTPS by default."""
import os

os.environ['WELLIFY_DEBUG'] = 'True'
from .settings import *  # noqa: F403, E402

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
