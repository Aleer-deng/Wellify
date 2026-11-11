from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views
from .social_views import SocialProvidersView

router = DefaultRouter()
router.register('challenges', views.ChallengeViewSet, basename='challenge')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('admin/users', views.AdminUserViewSet, basename='admin-user')
router.register('admin/rewards', views.AdminRewardViewSet, basename='admin-reward')
router.register('admin/challenges', views.AdminChallengeViewSet, basename='admin-challenge')
router.register('admin/activities', views.AdminActivityViewSet, basename='admin-activity')
router.register('admin/redemptions', views.AdminRedemptionViewSet, basename='admin-redemption')

urlpatterns = [
    path('status/', views.HealthView.as_view()),
    path('auth/csrf/', views.CSRFView.as_view()),
    path('auth/providers/', SocialProvidersView.as_view()),
    path('auth/register/', views.RegisterView.as_view()),
    path('auth/login/', views.LoginView.as_view()),
    path('auth/logout/', views.LogoutView.as_view()),
    path('profile/', views.ProfileView.as_view()),
    path('goals/', views.GoalsView.as_view()),
    path('health/sync/', views.SyncView.as_view()),
    path('health/records/', views.ActivityListView.as_view()),
    path('health/summary/', views.SummaryView.as_view()),
    path('rewards/', views.RewardListView.as_view()),
    path('rewards/balance/', views.BalanceView.as_view()),
    path('rewards/redeem/', views.RedeemView.as_view()),
    path('rewards/history/', views.HistoryView.as_view()),
    path('rewards/redemptions/', views.RedemptionListView.as_view()),
    path('subscription/', views.SubscriptionView.as_view()),
    path('wallet/', views.WalletView.as_view()),
    path('wallet/challenge/', views.WalletChallengeView.as_view()),
    path('wallet/verify/', views.WalletVerifyView.as_view()),
    path('admin/reports/', views.ReportsView.as_view()),
    path('', include(router.urls)),
]
