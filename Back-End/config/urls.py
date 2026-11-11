from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from wellness.forms import ResetPasswordForm

urlpatterns = [
    path('auth/password-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('auth/password-reset/sent/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('auth/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(form_class=ResetPasswordForm), name='password_reset_confirm'),
    path('auth/reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('admin/', admin.site.urls), path('api/v1/', include('wellness.urls')),
               path('api/v1/auth/social/', include('allauth.urls'))]
