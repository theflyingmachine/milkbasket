# Generated by Django 3.1.2 on 2023-01-01 18:00

import datetime

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('register', '0007_add_seller_contact'),
        ('customer', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginOTP',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False,
                                        verbose_name='ID')),
                ('otp_password', models.CharField(max_length=6)),
                ('login_attempt', models.DecimalField(decimal_places=0, max_digits=1)),
                ('generated_date', models.DateTimeField(default=datetime.datetime.now)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                               to='register.customer')),
            ],
        ),
    ]
