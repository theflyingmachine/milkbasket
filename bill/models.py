import uuid

from django.db import models
# Create your models here.
from jsonfield import JSONField

from register.models import Customer


class OnlinePayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    bill_number = models.CharField(max_length=25, null=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=25, null=False)
    status_msg = models.CharField(max_length=255, null=False, default='')
    token = models.CharField(max_length=255, null=False)
    order_id = models.CharField(max_length=255, null=False)
    online_transaction_id = models.CharField(max_length=255)
    raw_resp = JSONField(default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
