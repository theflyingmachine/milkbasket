# Generated by Django 3.1.2 on 2023-01-09 18:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('register', '0008_payment_refund_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='bill',
            name='mongo_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
