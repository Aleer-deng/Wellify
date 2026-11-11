from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from wellness.models import Challenge, Reward

class Command(BaseCommand):
    help = 'Create a sample catalog and challenge. Does not create users or issue points.'
    @transaction.atomic
    def handle(self, *args, **options):
        for name, cost, description in [
            ('Your next healthy sip', 350, 'Prototype smoothie reward; fulfillment is manual.'),
            ('Make room for movement', 800, 'Prototype yoga class reward; fulfillment is manual.'),
            ('A little everyday fuel', 1200, 'Prototype wellness basket; fulfillment is manual.'),
        ]:
            Reward.objects.get_or_create(name=name, defaults={'points_cost': cost, 'stock': 10, 'description': description})
        today = timezone.localdate()
        Challenge.objects.get_or_create(title='The 7-day step up', starts_on=today,
            defaults={'description': 'Accumulate 56,000 approved steps during the challenge.',
                      'ends_on': today + timedelta(days=6), 'target_steps': 56000, 'points': 500})
        self.stdout.write(self.style.SUCCESS('Sample catalog and challenge ready. No points or accounts created.'))
