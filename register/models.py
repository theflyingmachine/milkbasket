from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import ugettext_lazy as _


# Create your models here.


class Tenant(models.Model):
    tenant = models.OneToOneField(
        User,
        on_delete=models.PROTECT,
        primary_key=True, default=1,
    )
    download_pdf_pref = models.BooleanField(default=True)
    sms_pref = models.BooleanField(default=True)
    whatsapp_pref = models.BooleanField(default=True)
    whatsapp_direct_pref = models.BooleanField(default=True)
    email_pref = models.BooleanField(default=False)
    customers_bill_access = models.BooleanField(default=True)
    bill_till_date = models.BooleanField(default=True)
    accept_online_payment = models.BooleanField(default=False)
    milk_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, default=None)
    date_effective = models.DateTimeField(default=None, null=True)
    contact = models.CharField(max_length=10, null=True, blank=True, default=None)
    email = models.CharField(max_length=50, null=True, default=None, blank=True)


class Customer(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    name = models.CharField(max_length=50, unique=True)
    contact = models.CharField(max_length=10, null=True, blank=True, default='')
    email = models.CharField(max_length=50, null=True, default=None, blank=True)
    morning = models.BooleanField(default=True)
    evening = models.BooleanField(default=True)
    m_quantity = models.IntegerField(null=True, blank=True, default=None)
    e_quantity = models.IntegerField(null=True, blank=True, default=None)
    status = models.BooleanField(default=True)
    member_since = models.DateTimeField(auto_now_add=True, null=True)


class Payment(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    log_date = models.DateTimeField(auto_now_add=True, null=True)
    payment_mode = models.CharField(max_length=10, null=True, default='CASH', blank=True)
    transaction_id = models.CharField(max_length=50, null=True, default=None, blank=True)


class Register(models.Model):
    SCHEDULE_OPTIONS = [
        ('morning-yes', _('Morning Present')),
        ('morning-no', _('Morning Absent')),
        ('evening-yes', _('Evening Present')),
        ('evening-no', _('Evening Absent'))
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    log_date = models.DateTimeField()
    schedule = models.CharField(max_length=15, choices=SCHEDULE_OPTIONS, null=True, default=None)
    quantity = models.IntegerField(null=False, blank=False, default=None)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=None)
    paid = models.BooleanField(default=False)
    transaction_number = models.ForeignKey(Payment, default=None, null=True, blank=True,
                                           on_delete=models.PROTECT)


class Expense(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=1000, null=False, default='Description')
    log_date = models.DateTimeField(null=False, default=datetime.now)


class Balance(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    customer = models.OneToOneField(
        Customer,
        on_delete=models.PROTECT,
        primary_key=True,
    )
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    last_balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=None,
                                              null=True, blank=True)


class Income(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=1000, null=False, default='Description')
    log_date = models.DateTimeField(null=False, default=datetime.now)


class Bill(models.Model):
    customer_id = models.ForeignKey(Customer, on_delete=models.PROTECT)
    bill_number = models.CharField(max_length=25, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_last_data_date = models.DateTimeField(null=False)
    bill_generated_date = models.DateTimeField(null=False, default=datetime.now)
