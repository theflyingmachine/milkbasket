# Generated by Django 3.1.2 on 2021-07-08 12:47

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ('register', '0008_tenant_customers_bill_access'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='contact',
            field=models.CharField(blank=True, default='', max_length=10, null=True),
        ),
    ]
