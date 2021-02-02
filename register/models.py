from datetime import datetime

from django.contrib.auth.models import User
from django.db import models


# Create your models here.


class Customer(models.Model):
    name = models.CharField(max_length=50, unique=True)
    contact = models.CharField(max_length=10, null=True, default=None)
    email = models.CharField(max_length=50, null=True, default=None)
    morning = models.BooleanField(default=True)
    evening = models.BooleanField(default=True)
    quantity = models.FloatField(null=False, blank=False, default=None)
    status = models.BooleanField(default=True)
    member_since = models.DateTimeField(auto_now_add=True, null=True)


class Tenant(models.Model):
    tenant = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    download_pdf_pref = models.BooleanField(default=True)
    sms_pref = models.BooleanField(default=True)
    whatsapp_pref = models.BooleanField(default=True)
    email_pref = models.BooleanField(default=False)


class Milk(models.Model):
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date_effective = models.DateTimeField()


class Register(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)
    log_date = models.DateTimeField()
    schedule = models.CharField(max_length=15, null=True, default=None)
    quantity = models.FloatField(null=False, blank=False, default=None)
    current_price = models.DecimalField(max_digits=10, decimal_places=2, default=None)
    paid = models.BooleanField(default=False)


class Expense(models.Model):
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=1000, null=False, default='Description')
    log_date = models.DateTimeField(null=False, default=datetime.now)


class Payment(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    log_date = models.DateTimeField(auto_now_add=True, null=True)


class Balance(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    balance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)


class Income(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=1000, null=False, default='Description')
    log_date = models.DateTimeField(null=False, default=datetime.now)


class Bill(models.Model):
    customer_id = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)
    bill_number = models.CharField(max_length=25, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    bill_last_data_date = models.DateTimeField(null=False)
    bill_generated_date = models.DateTimeField(null=False, default=datetime.now)
