# Generated by Django 3.1.2 on 2021-02-27 12:48

from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ('register', '0006_tenant_whatsapp_direct_pref'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='bill_till_date',
            field=models.BooleanField(default=True),
        ),
    ]