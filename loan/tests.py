from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from loan.models import Loan, Transaction
from register.models import Tenant


class LoanTransactionApiTests(TestCase):
    def test_delete_transaction_route_matches_view_argument(self):
        user = User.objects.create_user(username='seller', password='test-password')
        tenant = Tenant.objects.create(tenant=user)
        loan = Loan.objects.create(
            tenant=tenant,
            name='Feed supplier',
            amount=Decimal('1000.00'),
            interest_rate=Decimal('0.00'),
            lending_date='2026-08-01T00:00:00',
        )
        transaction = Transaction.objects.create(
            loan_id=loan,
            transaction_amount=Decimal('100.00'),
            type='PRINCIPAL',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('delete_transaction_api', args=[transaction.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertFalse(Transaction.objects.filter(id=transaction.id).exists())
