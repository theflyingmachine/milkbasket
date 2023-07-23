# Generated by Django 4.2.1 on 2023-05-16 21:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("register", "0009_bill_mongo_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="bill",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="customer",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="expense",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="income",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="payment",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="register",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]