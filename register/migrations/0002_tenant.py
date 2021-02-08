# Generated by Django 3.1.2 on 2021-02-07 12:19

import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('register', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('tenant',
                 models.OneToOneField(default=1, on_delete=django.db.models.deletion.CASCADE,
                                      primary_key=True, serialize=False, to='auth.user')),
                ('download_pdf_pref', models.BooleanField(default=True)),
                ('sms_pref', models.BooleanField(default=True)),
                ('whatsapp_pref', models.BooleanField(default=True)),
                ('email_pref', models.BooleanField(default=False)),
                ('milk_price',
                 models.DecimalField(decimal_places=2, default=None, max_digits=10, null=True)),
                ('date_effective', models.DateTimeField(default=None, null=True)),
            ],
        ),
    ]