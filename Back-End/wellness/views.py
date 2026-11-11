import base64
import secrets
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.db import IntegrityError, transaction
from django.db.models import Sum, Q
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from .models import (Activity, AuditEvent, Challenge, Enrollment, Goal, LedgerEntry,
                     Notification, PointAccount, Redemption, Reward, Subscription, WalletLink)
from .serializers import (ActivitySerializer, AdminUserSerializer, ChallengeSerializer, GoalSerializer,
                          LoginSerializer, NotificationSerializer, ProfileSerializer, RedeemSerializer,
                          RedemptionSerializer, RegisterSerializer, RewardSerializer, SubscriptionSerializer)
from .services import account_for, claim_challenge, join_challenge, redeem_reward, review_activity

User = get_user_model()

class AuthThrottle(AnonRateThrottle):
    scope = 'auth'
    def get_cache_key(self, request, view):
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}

class CSRFView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'csrfToken': get_token(request)})

@method_decorator(csrf_protect, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=data['email'], email=data['email'],
                                                first_name=data['name'], password=data['password'])
                account_for(user)
                Goal.objects.bulk_create([Goal(user=user, period='daily', target=10000), Goal(user=user, period='weekly', target=70000)])
                Subscription.objects.create(user=user)
                Notification.objects.create(user=user, title='Welcome to Wellify', body='Set a goal and start your wellness journey.')
                AuditEvent.objects.create(actor=user, action='account.registered', object_id=str(user.pk))
        except IntegrityError:
            raise ValidationError({'email': 'This email is already registered.'})
        login(request._request, user, backend='django.contrib.auth.backends.ModelBackend')
        return Response({'user': ProfileSerializer(user).data, 'csrfToken': get_token(request)}, status=201)

@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthThrottle]
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        username = User.objects.filter(email__iexact=data['email']).values_list('username', flat=True).first() or data['email'].lower()
        user = authenticate(request=request._request, username=username, password=data['password'])
        if not user:
            return Response({'detail': 'Invalid email or password.'}, status=400)
        login(request._request, user)
        AuditEvent.objects.create(actor=user, action='account.login', object_id=str(user.pk))
        return Response({'user': ProfileSerializer(user).data, 'csrfToken': get_token(request)})

class LogoutView(APIView):
    def post(self, request):
        AuditEvent.objects.create(actor=request.user, action='account.logout', object_id=str(request.user.pk))
        logout(request._request)
        return Response(status=204)

class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    http_method_names = ['get', 'patch', 'head', 'options']
    def get_object(self):
        return self.request.user

class GoalsView(APIView):
    def get(self, request):
        return Response(GoalSerializer(Goal.objects.filter(user=request.user).order_by('period'), many=True).data)
    def put(self, request):
        serializer = GoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        goal, _ = Goal.objects.update_or_create(user=request.user, period=serializer.validated_data['period'],
                                                defaults={'target': serializer.validated_data['target']})
        return Response(GoalSerializer(goal).data)

class ActivityListView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    def get_queryset(self):
        return Activity.objects.filter(user=self.request.user)

class SyncView(APIView):
    def post(self, request):
        serializer = ActivitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Duplicate device record IDs are idempotent; conflicting payloads are rejected.
        with transaction.atomic():
            activity, created = Activity.objects.get_or_create(user=request.user, source=data['source'],
                external_id=data['external_id'], defaults={k: v for k, v in data.items() if k not in ['source', 'external_id']})
            if not created and any(getattr(activity, field) != data[field] for field in ['date', 'steps', 'active_minutes']):
                return Response({'detail': 'This external_id already identifies a different activity payload.'}, status=409)
            if created:
                AuditEvent.objects.create(actor=request.user, action='activity.submitted', object_id=str(activity.pk))
        return Response(ActivitySerializer(activity).data, status=201 if created else 200)

class SummaryView(APIView):
    def get(self, request):
        today = timezone.localdate()
        start = today - timedelta(days=today.weekday())
        approved = Activity.objects.filter(user=request.user, status='approved')
        daily = approved.filter(date=today).aggregate(steps=Sum('steps'), active_minutes=Sum('active_minutes'))
        weekly_steps = approved.filter(date__range=(start, today)).aggregate(total=Sum('steps'))['total'] or 0
        days = []
        grouped = {item['date']: item for item in approved.filter(date__range=(start, today)).values('date').annotate(steps=Sum('steps'), active_minutes=Sum('active_minutes'))}
        for offset in range(7):
            day = start + timedelta(days=offset)
            item = grouped.get(day, {})
            days.append({'date': day, 'steps': item.get('steps', 0), 'active_minutes': item.get('active_minutes', 0)})
        return Response({'date': today, 'steps': daily['steps'] or 0, 'active_minutes': daily['active_minutes'] or 0,
            'weekly_steps': weekly_steps, 'days': days, 'goals': GoalSerializer(Goal.objects.filter(user=request.user), many=True).data,
            'points': account_for(request.user).balance, 'pending_records': Activity.objects.filter(user=request.user, status='pending').count()})

class ChallengeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ChallengeSerializer
    queryset = Challenge.objects.filter(active=True)
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        enrollment = join_challenge(request.user, pk)
        return Response({'id': enrollment.pk, 'challenge_id': enrollment.challenge_id, 'completed_at': enrollment.completed_at})
    @action(detail=True, methods=['post'])
    def claim(self, request, pk=None):
        enrollment = claim_challenge(request.user, pk)
        return Response({'challenge_id': enrollment.challenge_id, 'completed_at': enrollment.completed_at})
    @action(detail=False, methods=['get'])
    def memberships(self, request):
        return Response(list(Enrollment.objects.filter(user=request.user).values('id', 'challenge_id', 'joined_at', 'completed_at')))

class RewardListView(generics.ListAPIView):
    serializer_class = RewardSerializer
    queryset = Reward.objects.filter(active=True)

class BalanceView(APIView):
    def get(self, request):
        return Response({'points': account_for(request.user).balance, 'currency': 'points', 'on_chain': False})

class HistoryView(generics.ListAPIView):
    class EntrySerializer(serializers.ModelSerializer):
        description = serializers.CharField(source='transaction.description')
        created_at = serializers.DateTimeField(source='transaction.created_at')
        class Meta:
            model = LedgerEntry
            fields = ['id', 'transaction_id', 'amount', 'description', 'created_at']
    serializer_class = EntrySerializer
    def get_queryset(self):
        return LedgerEntry.objects.filter(account__user=self.request.user).select_related('transaction').order_by('-transaction__created_at', '-id')

class RedeemView(APIView):
    def post(self, request):
        serializer = RedeemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        redemption, created = redeem_reward(request.user, data['reward_id'], data['idempotency_key'])
        return Response(RedemptionSerializer(redemption).data, status=201 if created else 200)

class RedemptionListView(generics.ListAPIView):
    serializer_class = RedemptionSerializer
    def get_queryset(self):
        return Redemption.objects.filter(user=self.request.user).select_related('reward')

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    http_method_names = ['get', 'patch', 'head', 'options']
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    def partial_update(self, request, *args, **kwargs):
        if set(request.data) != {'read'}:
            raise ValidationError('Only the read field can be updated.')
        return super().partial_update(request, *args, **kwargs)

class SubscriptionView(APIView):
    def get(self, request):
        subscription, _ = Subscription.objects.get_or_create(user=request.user)
        return Response(SubscriptionSerializer(subscription).data)
    def put(self, request):
        if set(request.data) != {'plan'}:
            raise ValidationError('Provide only a plan. Billing is simulated.')
        subscription, _ = Subscription.objects.get_or_create(user=request.user)
        serializer = SubscriptionSerializer(subscription, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer
    http_method_names = ['get', 'patch', 'head', 'options']
    def get_queryset(self):
        queryset = User.objects.order_by('id')
        query = self.request.query_params.get('search', '')
        return queryset.filter(Q(first_name__icontains=query) | Q(email__icontains=query))
    def perform_update(self, serializer):
        if serializer.instance.is_staff:
            raise ValidationError('Staff account status must be managed through Django admin.')
        serializer.save()
        AuditEvent.objects.create(actor=self.request.user, action='user.updated', object_id=str(serializer.instance.pk))

class AuditedAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']
    def perform_create(self, serializer):
        instance = serializer.save()
        AuditEvent.objects.create(actor=self.request.user, action=f'{instance._meta.model_name}.created', object_id=str(instance.pk))
    def perform_update(self, serializer):
        instance = serializer.save()
        AuditEvent.objects.create(actor=self.request.user, action=f'{instance._meta.model_name}.updated', object_id=str(instance.pk))

class AdminRewardViewSet(AuditedAdminViewSet):
    serializer_class = RewardSerializer
    queryset = Reward.objects.all()

class AdminChallengeViewSet(AuditedAdminViewSet):
    serializer_class = ChallengeSerializer
    queryset = Challenge.objects.all()

class AdminActivityViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = ActivitySerializer
    queryset = Activity.objects.all()
    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        self.get_object()
        if request.data.get('decision') not in ['approve', 'reject']:
            raise ValidationError('decision must be approve or reject.')
        activity = review_activity(pk, request.user, request.data['decision'] == 'approve')
        return Response(ActivitySerializer(activity).data)

class AdminRedemptionViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = RedemptionSerializer
    queryset = Redemption.objects.select_related('reward').all()
    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        with transaction.atomic():
            redemption = Redemption.objects.select_for_update().get(pk=self.get_object().pk)
            if redemption.status == 'requested':
                redemption.status = 'fulfilled'
                redemption.save(update_fields=['status'])
                AuditEvent.objects.create(actor=request.user, action='redemption.fulfilled', object_id=str(pk))
                Notification.objects.create(user=redemption.user, title='Reward fulfilled', body='Your reward has been marked fulfilled by an administrator.')
        return Response(RedemptionSerializer(redemption).data)

class ReportsView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        return Response({'users': User.objects.count(), 'active_users': User.objects.filter(is_active=True).count(),
            'pending_activities': Activity.objects.filter(status='pending').count(),
            'redemptions': Redemption.objects.count(), 'points_redeemed': Redemption.objects.aggregate(total=Sum('points_cost'))['total'] or 0,
            'ledger_net': LedgerEntry.objects.aggregate(total=Sum('amount'))['total'] or 0})

class WalletChallengeView(APIView):
    def post(self, request):
        # Domain/user binding, one use, five minute validity. No health data in the message.
        message = f'Wellify wallet verification\nHost: {request.get_host()}\nUser: {request.user.pk}\nNonce: {secrets.token_urlsafe(32)}'
        request.session['wallet_challenge'] = {'message': message, 'expires': time.time() + 300}
        return Response({'message': message, 'encoding': 'utf-8', 'expires_in': 300, 'signature': 'base64 Ed25519 over the exact UTF-8 message'})

class WalletVerifyView(APIView):
    def post(self, request):
        from stellar_sdk import Keypair
        challenge = request.session.pop('wallet_challenge', None)
        if not challenge or challenge['expires'] < time.time():
            raise ValidationError('Request a new wallet challenge.')
        address = request.data.get('address', '')
        signature = request.data.get('signature', '')
        try:
            Keypair.from_public_key(address).verify(challenge['message'].encode(), base64.b64decode(signature, validate=True))
        except Exception:
            raise ValidationError('Invalid wallet address or signature.')
        try:
            with transaction.atomic():
                link, _ = WalletLink.objects.update_or_create(user=request.user, defaults={'address': address})
        except IntegrityError:
            raise ValidationError('This wallet is already linked to another user.')
        return Response({'address': link.address, 'verified_at': link.verified_at, 'network': 'TESTNET'})

class WalletView(APIView):
    def get(self, request):
        from stellar_sdk import Server
        from stellar_sdk.exceptions import NotFoundError
        link = WalletLink.objects.filter(user=request.user).first()
        if not link:
            return Response({'address': None, 'network': 'TESTNET', 'balances': []})
        try:
            account = Server(settings.STELLAR_HORIZON_URL).accounts().account_id(link.address).call()
            balances = account['balances']
        except NotFoundError:
            return Response({'address': link.address, 'network': 'TESTNET', 'funded': False, 'balances': []})
        except Exception:
            return Response({'detail': 'Stellar Testnet is temporarily unavailable.'}, status=503)
        return Response({'address': link.address, 'network': 'TESTNET', 'funded': True, 'balances': balances,
                         'hrw_issuer': settings.HRW_ISSUER_PUBLIC_KEY})

class HealthView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        return Response({'status': 'ok', 'service': 'wellify-api'})
