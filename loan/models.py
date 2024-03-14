from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator
from django.db import models

from register.models import Tenant


class Loan(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT)
    name = models.CharField(max_length=50, null=False, blank=False)
    amount = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(1)])
    interest_rate = models.DecimalField(max_digits=4, decimal_places=2,
                                        validators=[MinValueValidator(0)])
    lending_date = models.DateTimeField(null=False, blank=False)
    status = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)


class Transaction(models.Model):
    CHOICES = (
        ('PRINCIPAL', 'Principal'),
        ('INTEREST', 'Interest'),
    )
    loan_id = models.ForeignKey(Loan, on_delete=models.CASCADE)
    transaction_amount = models.DecimalField(max_digits=8, decimal_places=2,
                                             validators=[MinValueValidator(1)])
    type = models.CharField(max_length=10, choices=CHOICES, default='INTEREST')
    transaction_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
