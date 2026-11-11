"""Run against PostgreSQL to exercise real row locks; SQLite cannot validate these guarantees."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError
from .models import PointAccount, Redemption, Reward
from .services import account_for, issue_points, redeem_reward

@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locking')
class RedemptionConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='concurrent@example.com', email='concurrent@example.com')
        account_for(self.user)
        PointAccount.objects.create(code='system:redemptions')
        issue_points(self.user, 500, 'concurrency:fund', 'Test funding')
        self.reward = Reward.objects.create(name='Last item', points_cost=350, stock=1)

    def requests(self, keys):
        barrier = Barrier(2)
        def attempt(key):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                item, created = redeem_reward(user, self.reward.pk, key)
                return str(item.pk), created
            except ValidationError:
                return 'rejected', False
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(attempt, keys))

    def test_simultaneous_redemptions_cannot_overdraw_or_oversell(self):
        results = self.requests([uuid.uuid4(), uuid.uuid4()])
        self.assertEqual(sum(item[0] != 'rejected' for item in results), 1)
        self.assertEqual(account_for(self.user).balance, 150)
        self.reward.refresh_from_db()
        self.assertEqual(self.reward.stock, 0)
        self.assertEqual(Redemption.objects.count(), 1)

    def test_simultaneous_duplicate_keys_return_the_same_redemption(self):
        key = uuid.uuid4()
        results = self.requests([key, key])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sum(item[1] for item in results), 1)
        self.assertEqual(account_for(self.user).balance, 150)
