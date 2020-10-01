from django.db import models

# Create your models here.


class Customer(models.Model):
    name = models.CharField(max_length=50)
    contact = models.CharField(max_length=10, null=True, default=None)
    email = models.CharField(max_length=50, null=True, default=None)
    morning = models.BooleanField(default=True)
    evening = models.BooleanField(default=True)
    quantity = models.FloatField(null=False, blank=False, default=None)
    status = models.BooleanField(default=True)
    member_since = models.DateTimeField(auto_now_add=True)


class Milk(models.Model):
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date_effective = models.DateTimeField()


class Register(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.DO_NOTHING)
    date = models.DateTimeField()
    morning = models.BooleanField(default=False)
    evening = models.BooleanField(default=False)
    quantity = models.FloatField(null=False, blank=False, default=None)






