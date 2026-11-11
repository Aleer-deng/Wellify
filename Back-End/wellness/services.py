from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError, NotFound
from .models import (Activity, AuditEvent, Challenge, Enrollment, LedgerEntry,
                     LedgerTransaction, Notification, PointAccount, Redemption, Reward)

def account_for(user):
    return PointAccount.objects.get_or_create(user=user, defaults={'code': f'user:{user.pk}'})[0]

@transaction.atomic
def transfer(source, destination, amount, event_key, description):
    """Only posting path: two equal/opposite entries and cached balances, one transaction."""
    if amount <= 0 or source.pk == destination.pk:
        raise ValidationError('Invalid transfer.')
    # Lock both accounts in a stable order; conditional debit also protects SQLite writes.
    list(PointAccount.objects.select_for_update().filter(pk__in=[source.pk, destination.pk]).order_by('pk'))
    existing = LedgerTransaction.objects.filter(event_key=event_key).first()
    if existing:
        return existing
    debit = PointAccount.objects.filter(pk=source.pk)
    if source.user_id:
        debit = debit.filter(balance__gte=amount)
    if debit.update(balance=F('balance') - amount) != 1:
        raise ValidationError('Insufficient points.')
    PointAccount.objects.filter(pk=destination.pk).update(balance=F('balance') + amount)
    ledger = LedgerTransaction.objects.create(event_key=event_key, description=description)
    LedgerEntry.objects.bulk_create([
        LedgerEntry(transaction=ledger, account=source, amount=-amount),
        LedgerEntry(transaction=ledger, account=destination, amount=amount),
    ])
    return ledger

def issue_points(user, amount, event_key, description):
    issuer, _ = PointAccount.objects.get_or_create(code='system:issuance')
    return transfer(issuer, account_for(user), amount, event_key, description)

@transaction.atomic
def review_activity(activity_id, actor, approve):
    activity = Activity.objects.select_for_update().select_related('user').get(pk=activity_id)
    if activity.status != 'pending':
        return activity
    # Lock the user's account to serialize approvals and prevent splitting payloads to beat caps.
    account = account_for(activity.user)
    PointAccount.objects.select_for_update().get(pk=account.pk)
    daily = Activity.objects.filter(user=activity.user, date=activity.date, status='approved').aggregate(
        steps=Sum('steps'), minutes=Sum('active_minutes'))
    previous_steps = daily['steps'] or 0
    if approve and (previous_steps + activity.steps > 100000 or (daily['minutes'] or 0) + activity.active_minutes > 1440):
        raise ValidationError('Approved daily totals would exceed activity limits.')
    activity.status = 'approved' if approve else 'rejected'
    activity.reviewed_by = actor
    activity.reviewed_at = timezone.now()
    activity.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    # One point per 100 steps, based on cumulative daily steps (no per-payload rounding exploit).
    points = (previous_steps + activity.steps) // 100 - previous_steps // 100 if approve else 0
    if points:
        issue_points(activity.user, points, f'activity:{activity.pk}', 'Verified activity reward')
    Notification.objects.create(user=activity.user, title='Activity reviewed',
        body=f'Your activity was {activity.status}. Points awarded: {points}.')
    AuditEvent.objects.create(actor=actor, action=f'activity.{activity.status}', object_id=str(activity.pk))
    return activity

@transaction.atomic
def join_challenge(user, challenge_id):
    try:
        challenge = Challenge.objects.select_for_update().get(pk=challenge_id, active=True)
    except Challenge.DoesNotExist:
        raise NotFound('Active challenge not found.')
    if challenge.ends_on < timezone.localdate():
        raise ValidationError('This challenge has ended.')
    return Enrollment.objects.get_or_create(user=user, challenge=challenge)[0]

@transaction.atomic
def claim_challenge(user, challenge_id):
    try:
        enrollment = Enrollment.objects.select_for_update().select_related('challenge').get(user=user, challenge_id=challenge_id)
    except Enrollment.DoesNotExist:
        raise ValidationError('Join the challenge before claiming it.')
    if enrollment.completed_at:
        return enrollment
    challenge = enrollment.challenge
    if not challenge.active:
        raise ValidationError('Challenge is inactive.')
    # Only activity dated on/after joining counts; dates are the source granularity.
    start = max(challenge.starts_on, timezone.localtime(enrollment.joined_at).date())
    steps = Activity.objects.filter(user=user, status='approved', date__range=(start, challenge.ends_on)).aggregate(total=Sum('steps'))['total'] or 0
    if steps < challenge.target_steps:
        raise ValidationError('Not enough approved steps to complete this challenge.')
    issue_points(user, challenge.points, f'challenge:{enrollment.pk}', f'Challenge: {challenge.title}')
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=['completed_at'])
    Notification.objects.create(user=user, title='Challenge completed', body=f'You earned {challenge.points} points.')
    AuditEvent.objects.create(actor=user, action='challenge.completed', object_id=str(challenge_id))
    return enrollment

@transaction.atomic
def redeem_reward(user, reward_id, key):
    account = account_for(user)
    PointAccount.objects.select_for_update().get(pk=account.pk)
    existing = Redemption.objects.filter(user=user, idempotency_key=key).first()
    if existing:
        if existing.reward_id != reward_id:
            raise ValidationError('Idempotency key was already used for a different reward.')
        return existing, False
    try:
        reward = Reward.objects.select_for_update().get(pk=reward_id, active=True)
    except Reward.DoesNotExist:
        raise NotFound('Available reward not found.')
    if Reward.objects.filter(pk=reward.pk, stock__gt=0, active=True).update(stock=F('stock') - 1) != 1:
        raise ValidationError('Reward is out of stock.')
    treasury, _ = PointAccount.objects.get_or_create(code='system:redemptions')
    ledger = transfer(account, treasury, reward.points_cost, f'redemption:{user.pk}:{key}', f'Redeemed: {reward.name}')
    redemption = Redemption.objects.create(user=user, reward=reward, points_cost=reward.points_cost,
                                          idempotency_key=key, transaction=ledger)
    Notification.objects.create(user=user, title='Redemption requested', body=f'{reward.name}: {reward.points_cost} points. Awaiting fulfillment.')
    AuditEvent.objects.create(actor=user, action='reward.redeemed', object_id=str(redemption.pk))
    return redemption, True
