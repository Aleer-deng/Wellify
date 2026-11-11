import base64
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from stellar_sdk import Keypair
from .models import (Activity, Challenge, Enrollment, LedgerEntry, LedgerTransaction, Notification,
                     PointAccount, Redemption, Reward, WalletLink)
from .services import account_for, issue_points, redeem_reward, review_activity

User = get_user_model()
PASSWORD = 'Long-Wellify-Test-Pass-84!'

class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
    def csrf(self):
        token = self.client.get('/api/v1/auth/csrf/').data['csrfToken']
        self.client.credentials(HTTP_X_CSRFTOKEN=token)
    def register(self):
        return self.client.post('/api/v1/auth/register/', {'name': 'Jamie', 'email': 'Jamie@example.com', 'password': PASSWORD}, format='json')
    def test_registration_requires_csrf(self):
        self.assertEqual(self.register().status_code, 403)
        self.assertEqual(User.objects.count(), 0)
    def test_registration_hashes_password_and_creates_zero_balance(self):
        self.csrf()
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get()
        self.assertEqual(user.email, 'jamie@example.com')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn('password', response.data['user'])
        self.assertEqual(account_for(user).balance, 0)
        self.assertEqual(self.client.get('/api/v1/profile/').status_code, 200)
    def test_weak_password_and_case_duplicate_rejected(self):
        self.csrf()
        self.assertEqual(self.client.post('/api/v1/auth/register/', {'name':'Jamie','email':'jamie@example.com','password':'123'},format='json').status_code,400)
        self.assertEqual(self.register().status_code,201)
        self.csrf()
        self.assertEqual(self.register().status_code,400)
    def test_login_csrf_logout_and_inactive_user(self):
        user = User.objects.create_user(username='jamie@example.com', email='jamie@example.com', password=PASSWORD)
        payload = {'email': user.email, 'password': PASSWORD}
        self.assertEqual(self.client.post('/api/v1/auth/login/', payload, format='json').status_code,403)
        self.csrf()
        response = self.client.post('/api/v1/auth/login/', payload, format='json')
        self.assertEqual(response.status_code,200)
        self.client.credentials(HTTP_X_CSRFTOKEN=response.data['csrfToken'])
        self.assertEqual(self.client.post('/api/v1/auth/logout/').status_code,204)
        self.assertEqual(self.client.get('/api/v1/profile/').status_code,403)
        user.is_active=False; user.save()
        self.csrf()
        self.assertEqual(self.client.post('/api/v1/auth/login/',payload,format='json').status_code,400)
    def test_admin_username_can_login_by_email(self):
        User.objects.create_superuser(username='administrator',email='admin@example.com',password=PASSWORD)
        self.csrf()
        response=self.client.post('/api/v1/auth/login/',{'email':'admin@example.com','password':PASSWORD},format='json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data['user']['is_staff'])
    def test_login_accepts_django_username(self):
        User.objects.create_superuser(username='wellify_admin_test',email='admin-test@example.com',password=PASSWORD)
        self.csrf()
        response=self.client.post('/api/v1/auth/login/',{'email':'wellify_admin_test','password':PASSWORD},format='json')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.data['user']['is_staff'])
    def test_anonymous_access_denied(self):
        for path in ['profile/', 'health/summary/', 'rewards/balance/', 'admin/reports/', 'wallet/']:
            self.assertEqual(self.client.get('/api/v1/'+path).status_code,403)
    def test_authentication_rate_limit(self):
        self.csrf()
        for _ in range(10):
            self.client.post('/api/v1/auth/login/', {'email':'none@example.com','password':'wrong'},format='json')
        self.assertEqual(self.client.post('/api/v1/auth/login/', {'email':'none@example.com','password':'wrong'},format='json').status_code,429)

class APITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user(username='jamie@example.com',email='jamie@example.com',password=PASSWORD)
        self.other=User.objects.create_user(username='other@example.com',email='other@example.com',password=PASSWORD)
        self.staff=User.objects.create_user(username='staff@example.com',email='staff@example.com',password=PASSWORD,is_staff=True)
        self.client.force_authenticate(self.user)
    def activity(self, **kwargs):
        data={'user':self.user,'external_id':str(uuid.uuid4()),'source':'manual','date':timezone.localdate(),'steps':10000,'active_minutes':40}
        data.update(kwargs)
        return Activity.objects.create(**data)
    def test_sync_is_pending_and_duplicate_is_idempotent(self):
        data={'external_id':'watch-1','source':'health_connect','date':str(timezone.localdate()),'steps':1000,'active_minutes':10,'status':'approved'}
        response=self.client.post('/api/v1/health/sync/',data,format='json')
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.data['status'],'pending')
        self.assertEqual(account_for(self.user).balance,0)
        self.assertEqual(self.client.post('/api/v1/health/sync/',data,format='json').status_code,200)
        data['steps']=2000
        self.assertEqual(self.client.post('/api/v1/health/sync/',data,format='json').status_code,409)
        self.assertEqual(Activity.objects.count(),1)
    def test_activity_bounds_and_future_dates_rejected(self):
        for steps,date in [(100001,timezone.localdate()),(-1,timezone.localdate()),(10,timezone.localdate()+timedelta(days=1))]:
            response=self.client.post('/api/v1/health/sync/',{'external_id':'bad','source':'manual','date':str(date),'steps':steps},format='json')
            self.assertEqual(response.status_code,400)
    def test_review_requires_staff_and_only_awards_once(self):
        record=self.activity()
        url=f'/api/v1/admin/activities/{record.pk}/review/'
        self.assertEqual(self.client.post(url,{'decision':'approve'}).status_code,403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(url,{'decision':'approve'}).status_code,200)
        self.assertEqual(self.client.post(url,{'decision':'approve'}).status_code,200)
        self.assertEqual(account_for(self.user).balance,100)
        self.assertEqual(LedgerEntry.objects.count(),2)
        self.assertEqual(LedgerEntry.objects.aggregate(total=Sum('amount'))['total'],0)
        call_command('check_ledger',verbosity=0)
    def test_split_activity_rounding_and_daily_cap(self):
        for steps in [50,50]:
            review_activity(self.activity(steps=steps,active_minutes=0).pk,self.staff,True)
        self.assertEqual(account_for(self.user).balance,1)
        large=self.activity(steps=100000)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.post(f'/api/v1/admin/activities/{large.pk}/review/',{'decision':'approve'}).status_code,400)
        large.refresh_from_db();self.assertEqual(large.status,'pending')
    def test_rejected_activity_no_award(self):
        review_activity(self.activity().pk,self.staff,False)
        self.assertEqual(account_for(self.user).balance,0)
    def test_user_data_isolation(self):
        self.activity(user=self.other)
        notice=Notification.objects.create(user=self.other,title='Private',body='Private')
        self.assertEqual(self.client.get('/api/v1/health/records/').data['count'],0)
        self.assertEqual(self.client.patch(f'/api/v1/notifications/{notice.pk}/',{'read':True},format='json').status_code,404)
    def test_summary_only_counts_approved_records(self):
        self.activity(steps=5000)
        review_activity(self.activity(steps=1000).pk,self.staff,True)
        data=self.client.get('/api/v1/health/summary/').data
        self.assertEqual(data['steps'],1000)
        self.assertEqual(data['pending_records'],1)
    def test_goals_validation_and_update(self):
        self.assertEqual(self.client.put('/api/v1/goals/',{'period':'daily','target':0},format='json').status_code,400)
        for target in [7000,8000]:
            self.assertEqual(self.client.put('/api/v1/goals/',{'period':'daily','target':target},format='json').status_code,200)
        self.assertEqual(self.client.get('/api/v1/goals/').data[0]['target'],8000)
    def test_challenge_join_and_claim_once(self):
        today=timezone.localdate()
        challenge=Challenge.objects.create(title='Walk',description='Walk',starts_on=today,ends_on=today+timedelta(days=7),target_steps=1000,points=50)
        base=f'/api/v1/challenges/{challenge.pk}/'
        self.assertEqual(self.client.post(base+'claim/').status_code,400)
        self.assertEqual(self.client.post(base+'join/').status_code,200)
        self.assertEqual(self.client.post(base+'claim/').status_code,400)
        review_activity(self.activity(steps=1000).pk,self.staff,True)
        for _ in range(2):self.assertEqual(self.client.post(base+'claim/').status_code,200)
        self.assertEqual(account_for(self.user).balance,60)
        self.assertEqual(Enrollment.objects.count(),1)
    def test_redemption_retry_no_double_charge(self):
        issue_points(self.user,500,'test:fund','Test funding')
        reward=Reward.objects.create(name='Smoothie',points_cost=350,stock=2)
        data={'reward_id':reward.pk,'idempotency_key':str(uuid.uuid4())}
        first=self.client.post('/api/v1/rewards/redeem/',data,format='json')
        second=self.client.post('/api/v1/rewards/redeem/',data,format='json')
        self.assertEqual(first.status_code,201);self.assertEqual(second.status_code,200)
        self.assertEqual(first.data['id'],second.data['id'])
        self.assertEqual(account_for(self.user).balance,150)
        reward.refresh_from_db();self.assertEqual(reward.stock,1)
        self.assertEqual(Redemption.objects.count(),1)
        call_command('check_ledger',verbosity=0)
    def test_insufficient_balance_rolls_back_stock_and_ledger(self):
        reward=Reward.objects.create(name='Smoothie',points_cost=350,stock=2)
        response=self.client.post('/api/v1/rewards/redeem/',{'reward_id':reward.pk,'idempotency_key':str(uuid.uuid4())},format='json')
        self.assertEqual(response.status_code,400)
        reward.refresh_from_db();self.assertEqual(reward.stock,2)
        self.assertEqual(Redemption.objects.count(),0);self.assertEqual(LedgerTransaction.objects.count(),0)
    def test_out_of_stock_and_inactive_rewards(self):
        issue_points(self.user,500,'test:fund','Test funding')
        reward=Reward.objects.create(name='Unavailable',points_cost=10,stock=0)
        self.assertEqual(self.client.post('/api/v1/rewards/redeem/',{'reward_id':reward.pk,'idempotency_key':str(uuid.uuid4())},format='json').status_code,400)
        reward.active=False;reward.save()
        self.assertEqual(self.client.post('/api/v1/rewards/redeem/',{'reward_id':reward.pk,'idempotency_key':str(uuid.uuid4())},format='json').status_code,404)
    def test_key_cannot_be_reused_for_other_reward(self):
        issue_points(self.user,500,'test:fund','Test funding')
        one=Reward.objects.create(name='One',points_cost=10,stock=2)
        two=Reward.objects.create(name='Two',points_cost=10,stock=2)
        key=uuid.uuid4()
        redeem_reward(self.user,one.pk,key)
        self.assertEqual(self.client.post('/api/v1/rewards/redeem/',{'reward_id':two.pk,'idempotency_key':str(key)},format='json').status_code,400)
    def test_profile_cannot_escalate_privileges(self):
        response=self.client.patch('/api/v1/profile/',{'name':'Jamie Updated','is_staff':True},format='json')
        self.assertEqual(response.status_code,200)
        self.user.refresh_from_db();self.assertFalse(self.user.is_staff)
        self.assertEqual(self.user.first_name,'Jamie Updated')
        self.assertEqual(self.client.get('/api/v1/admin/reports/').status_code,403)
    def test_subscription_is_simulated_and_validated(self):
        self.assertEqual(self.client.put('/api/v1/subscription/',{'plan':'plus'},format='json').status_code,200)
        self.assertTrue(self.client.get('/api/v1/subscription/').data['simulated'])
        self.assertEqual(self.client.put('/api/v1/subscription/',{'plan':'plus','simulated':False},format='json').status_code,400)
    def test_notification_read_update(self):
        notice=Notification.objects.create(user=self.user,title='Hello',body='Hello')
        self.assertEqual(self.client.patch(f'/api/v1/notifications/{notice.pk}/',{'read':True},format='json').status_code,200)
        notice.refresh_from_db();self.assertTrue(notice.read)
    def test_staff_reward_management_and_fulfillment(self):
        self.client.force_authenticate(self.staff)
        response=self.client.post('/api/v1/admin/rewards/',{'name':'New reward','points_cost':10,'stock':2},format='json')
        self.assertEqual(response.status_code,201)
        issue_points(self.user,100,'test:fund','Test funding')
        redemption,_=redeem_reward(self.user,response.data['id'],uuid.uuid4())
        self.assertEqual(self.client.post(f'/api/v1/admin/redemptions/{redemption.pk}/fulfill/').status_code,200)
        redemption.refresh_from_db();self.assertEqual(redemption.status,'fulfilled')
    def test_wallet_signature_is_one_use_and_user_bound(self):
        key=Keypair.random()
        challenge=self.client.post('/api/v1/wallet/challenge/').data['message']
        signature=base64.b64encode(key.sign(challenge.encode())).decode()
        data={'address':key.public_key,'signature':signature}
        self.assertEqual(self.client.post('/api/v1/wallet/verify/',data,format='json').status_code,200)
        self.assertEqual(self.client.post('/api/v1/wallet/verify/',data,format='json').status_code,400)
        self.assertEqual(WalletLink.objects.get(user=self.user).address,key.public_key)
    def test_invalid_wallet_signature_rejected(self):
        self.client.post('/api/v1/wallet/challenge/')
        self.assertEqual(self.client.post('/api/v1/wallet/verify/',{'address':'bad','signature':'bad'},format='json').status_code,400)
        self.assertEqual(WalletLink.objects.count(),0)
    def test_wallet_network_error_is_not_a_server_crash(self):
        WalletLink.objects.create(user=self.user,address=Keypair.random().public_key)
        with patch('stellar_sdk.Server') as server:
            server.return_value.accounts.return_value.account_id.return_value.call.side_effect=RuntimeError('offline')
            self.assertEqual(self.client.get('/api/v1/wallet/').status_code,503)

class SeedTests(TestCase):
    def test_seed_is_repeatable_without_free_points(self):
        call_command('seed_demo',verbosity=0);call_command('seed_demo',verbosity=0)
        self.assertEqual(Reward.objects.count(),3)
        self.assertEqual(Challenge.objects.count(),1)
        self.assertEqual(User.objects.count(),0)
        self.assertEqual(LedgerEntry.objects.count(),0)
