from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from register.models import Customer, Payment, Register, Tenant


class BillingIsolationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller', password='test-password')
        self.other_seller = User.objects.create_user(username='other-seller', password='test-password')
        self.tenant = Tenant.objects.create(tenant=self.seller, milk_price=Decimal('60.00'))
        self.other_tenant = Tenant.objects.create(tenant=self.other_seller, milk_price=Decimal('60.00'))
        self.customer = Customer.objects.create(tenant=self.tenant, name='Alice')
        self.other_customer = Customer.objects.create(tenant=self.other_tenant, name='Bob')

    def test_manual_entry_cannot_target_another_tenants_customer(self):
        self.client.force_login(self.seller)

        response = self.client.post(reverse('view_add_entry'), {
            'id': self.other_customer.id,
            'log_date': '01 August, 2026',
            'attendance': '1',
            'schedule': 'morning',
            'quantity': '500',
        })

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Register.objects.exists())

    def test_bill_generation_requires_login_and_customer_ownership(self):
        bill_url = reverse('print_bill', args=[self.other_customer.id])
        self.assertEqual(self.client.get(bill_url).status_code, 302)

        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(bill_url).status_code, 404)

    def test_only_one_delivery_period_entry_is_allowed_per_day(self):
        Register.objects.create(
            tenant=self.tenant,
            customer=self.customer,
            log_date=datetime(2026, 8, 1),
            schedule='morning-no',
            quantity=0,
            current_price=Decimal('60.00'),
        )

        with self.assertRaises(IntegrityError):
            Register.objects.create(
                tenant=self.tenant,
                customer=self.customer,
                log_date=datetime(2026, 8, 1),
                schedule='morning-yes',
                quantity=500,
                current_price=Decimal('60.00'),
            )


class PaymentCooldownTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller', password='test-password')
        self.tenant = Tenant.objects.create(tenant=self.seller, milk_price=Decimal('60.00'))
        self.customer = Customer.objects.create(tenant=self.tenant, name='Alice')
        self.client.force_login(self.seller)

    def test_rejects_second_payment_for_same_customer_within_cooldown(self):
        Payment.objects.create(tenant=self.tenant, customer=self.customer, amount=Decimal('100.00'))

        response = self.client.post(reverse('accept_payment'), {
            'c_id': self.customer.id,
            'c_payment': '100.00',
            'sms-notification': '0',
        })

        self.assertRedirects(response, reverse('view_account'))
        self.assertEqual(Payment.objects.filter(customer=self.customer).count(), 1)
        payment_messages = list(messages.get_messages(response.wsgi_request))
        self.assertEqual(payment_messages[0].tags, 'warning')
        self.assertIn('Payment of Rs. 100.00 from Alice was already accepted',
                      str(payment_messages[0]))
        self.assertIn('try again in', str(payment_messages[0]))
