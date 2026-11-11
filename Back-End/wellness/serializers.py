from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from .models import Activity, Challenge, Goal, Notification, Redemption, Reward, Subscription

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='first_name', max_length=80)
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'city', 'bio', 'is_staff']
        read_only_fields = ['id', 'email', 'is_staff']

class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=80)
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value
    def validate(self, attrs):
        user = User(username=attrs['email'], email=attrs['email'], first_name=attrs['name'])
        try:
            validate_password(attrs['password'], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': error.messages})
        return attrs

class LoginSerializer(serializers.Serializer):
    # Backward-compatible field name; login accepts an email or Django username.
    email = serializers.CharField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

class GoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Goal
        fields = ['id', 'period', 'target']
        read_only_fields = ['id']
    def validate(self, attrs):
        limit = 100000 if attrs['period'] == 'daily' else 700000
        if not 100 <= attrs['target'] <= limit:
            raise serializers.ValidationError({'target': f'Target must be between 100 and {limit}.'})
        return attrs

class ActivitySerializer(serializers.ModelSerializer):
    steps = serializers.IntegerField(min_value=0, max_value=100000)
    active_minutes = serializers.IntegerField(min_value=0, max_value=1440, default=0)
    source = serializers.ChoiceField(choices=['manual', 'health_connect', 'healthkit', 'fitbit', 'garmin'])
    class Meta:
        model = Activity
        fields = ['id', 'user_id', 'external_id', 'source', 'date', 'steps', 'active_minutes', 'status', 'created_at']
        read_only_fields = ['id', 'user_id', 'status', 'created_at']
        validators = []
    def validate_date(self, value):
        today = timezone.localdate()
        if value > today or (today - value).days > 31:
            raise serializers.ValidationError('Activity must be dated within the last 31 days, not in the future.')
        return value

class ChallengeSerializer(serializers.ModelSerializer):
    target_steps = serializers.IntegerField(min_value=1, max_value=10000000)
    points = serializers.IntegerField(min_value=1, max_value=10000)
    class Meta:
        model = Challenge
        fields = ['id', 'title', 'description', 'starts_on', 'ends_on', 'target_steps', 'points', 'active']
    def validate(self, attrs):
        start = attrs.get('starts_on', getattr(self.instance, 'starts_on', None))
        end = attrs.get('ends_on', getattr(self.instance, 'ends_on', None))
        if start and end and end < start:
            raise serializers.ValidationError('Challenge end must be on or after its start.')
        return attrs

class RewardSerializer(serializers.ModelSerializer):
    points_cost = serializers.IntegerField(min_value=1, max_value=1000000)
    stock = serializers.IntegerField(min_value=0, max_value=1000000)
    class Meta:
        model = Reward
        fields = ['id', 'name', 'description', 'points_cost', 'stock', 'active']

class RedeemSerializer(serializers.Serializer):
    reward_id = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.UUIDField()

class RedemptionSerializer(serializers.ModelSerializer):
    reward_name = serializers.CharField(source='reward.name', read_only=True)
    class Meta:
        model = Redemption
        fields = ['id', 'user_id', 'reward_id', 'reward_name', 'points_cost', 'status', 'created_at', 'transaction_id']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'body', 'read', 'created_at']
        read_only_fields = ['id', 'title', 'body', 'created_at']

class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ['plan', 'simulated', 'updated_at']
        read_only_fields = ['simulated', 'updated_at']

class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'email', 'is_active', 'date_joined']
        read_only_fields = ['id', 'first_name', 'email', 'date_joined']
