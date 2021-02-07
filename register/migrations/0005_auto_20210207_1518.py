# Generated by Django 3.1.2 on 2021-02-07 15:18

import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ('register', '0004_delete_milk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='balance',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
        migrations.AlterField(
            model_name='expense',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
        migrations.AlterField(
            model_name='income',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
        migrations.AlterField(
            model_name='payment',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
        migrations.AlterField(
            model_name='register',
            name='tenant',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING,
                                    to='register.tenant'),
        ),
    ]
