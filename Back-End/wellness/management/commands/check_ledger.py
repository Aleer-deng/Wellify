from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count
from wellness.models import LedgerTransaction, PointAccount

class Command(BaseCommand):
    help = 'Read-only reconciliation of all ledger postings and cached account balances.'
    def handle(self, *args, **options):
        errors = []
        for item in LedgerTransaction.objects.annotate(net=Sum('entries__amount'), postings=Count('entries')):
            if item.net != 0 or item.postings != 2:
                errors.append(f'Transaction {item.pk} is unbalanced or has an invalid posting count.')
        for account in PointAccount.objects.annotate(posted=Sum('entries__amount')):
            if account.balance != (account.posted or 0):
                errors.append(f'Account {account.pk} cached balance does not match postings.')
        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(self.style.SUCCESS('Ledger reconciles: all postings balance and account totals match.'))
