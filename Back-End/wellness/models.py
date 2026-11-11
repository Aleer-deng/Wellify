import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

class User(AbstractUser):
    email = models.EmailField(unique=True)
    city = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)

class Goal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    period = models.CharField(max_length=6, choices=[('daily', 'Daily'), ('weekly', 'Weekly')])
    target = models.PositiveIntegerField(default=10000)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'period'], name='one_goal_per_period'),
                       models.CheckConstraint(condition=Q(target__gte=100, target__lte=700000), name='valid_goal_target')]

class Activity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    external_id = models.CharField(max_length=100)
    source = models.CharField(max_length=40)
    date = models.DateField()
    steps = models.PositiveIntegerField()
    active_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_activities')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-date', '-id']
        constraints = [models.UniqueConstraint(fields=['user', 'source', 'external_id'], name='unique_activity_payload'),
                       models.CheckConstraint(condition=Q(steps__lte=100000, active_minutes__lte=1440), name='plausible_activity_bounds')]

class Challenge(models.Model):
    title = models.CharField(max_length=120)
    description = models.TextField(max_length=1000)
    starts_on = models.DateField()
    ends_on = models.DateField()
    target_steps = models.PositiveIntegerField()
    points = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    class Meta:
        ordering = ['-starts_on', '-id']
        constraints = [models.CheckConstraint(condition=Q(ends_on__gte=models.F('starts_on')), name='challenge_date_order'),
                       models.CheckConstraint(condition=Q(target_steps__gt=0, points__gt=0), name='positive_challenge_values')]

class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    challenge = models.ForeignKey(Challenge, on_delete=models.PROTECT)
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'challenge'], name='unique_enrollment')]

class PointAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    code = models.CharField(max_length=100, unique=True)
    balance = models.BigIntegerField(default=0)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(user__isnull=True) | Q(balance__gte=0), name='nonnegative_user_balance')]

class LedgerTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=180, unique=True)
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class LedgerEntry(models.Model):
    transaction = models.ForeignKey(LedgerTransaction, on_delete=models.PROTECT, related_name='entries')
    account = models.ForeignKey(PointAccount, on_delete=models.PROTECT, related_name='entries')
    amount = models.BigIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['transaction', 'account'], name='unique_account_transaction'),
                       models.CheckConstraint(condition=~Q(amount=0), name='nonzero_ledger_entry')]

class Reward(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=1000, blank=True)
    points_cost = models.PositiveIntegerField()
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    class Meta:
        ordering = ['id']
        constraints = [models.CheckConstraint(condition=Q(points_cost__gt=0), name='positive_reward_cost')]

class Redemption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reward = models.ForeignKey(Reward, on_delete=models.PROTECT)
    points_cost = models.PositiveIntegerField()
    idempotency_key = models.UUIDField()
    transaction = models.OneToOneField(LedgerTransaction, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, default='requested', choices=[('requested', 'Requested'), ('fulfilled', 'Fulfilled')])
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'idempotency_key'], name='unique_redemption_request')]

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    body = models.TextField(max_length=1000)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class Subscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20, choices=[('explorer', 'Explorer'), ('plus', 'Plus'), ('community', 'Community')], default='explorer')
    simulated = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=80)
    object_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']

class WalletLink(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    address = models.CharField(max_length=56, unique=True)
    verified_at = models.DateTimeField(auto_now=True)
