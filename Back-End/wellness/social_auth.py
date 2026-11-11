from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect
from .models import AuditEvent, Goal, Notification, Subscription
from .services import account_for


def login_error(code):
    return ImmediateHttpResponse(HttpResponseRedirect(
        settings.WELLIFY_FRONTEND_URL + '/?auth_error=' + code))


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # Password registrations go through our validated API only.
        return False

    def get_login_redirect_url(self, request):
        return settings.LOGIN_REDIRECT_URL


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            if not sociallogin.user.is_active:
                raise login_error('inactive')
            return
        email = (sociallogin.user.email or '').strip().lower()
        if not email:
            raise login_error('email_required')
        # Never attach a provider to an existing account just by email match.
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise login_error('existing_account')
        sociallogin.user.email = email

    def save_user(self, request, sociallogin, form=None):
        try:
            with transaction.atomic():
                user = super().save_user(request, sociallogin, form)
                account_for(user)
                Goal.objects.bulk_create([
                    Goal(user=user, period='daily', target=10000),
                    Goal(user=user, period='weekly', target=70000),
                ])
                Subscription.objects.create(user=user)
                Notification.objects.create(user=user, title='Welcome to Wellify',
                                            body='Set a goal and start your wellness journey.')
                AuditEvent.objects.create(actor=user, action='account.registered', object_id=str(user.pk))
                return user
        except IntegrityError:
            raise login_error('existing_account')

    def on_authentication_error(self, request, provider, error=None, exception=None, extra_context=None):
        raise login_error('provider_failed')
