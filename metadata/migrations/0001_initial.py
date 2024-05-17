# Generated by Django 4.2.1 on 2024-05-05 17:22

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MBMetadataSync",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("report_name", models.CharField(max_length=500)),
                ("app_name", models.CharField(max_length=500)),
                ("model_name", models.CharField(max_length=500)),
                ("db_table", models.CharField(max_length=500)),
                ("table_filters", models.CharField(max_length=3500, null=True)),
                ("table_update_on", models.CharField(max_length=3500, null=True)),
                ("inherit_parent_filter", models.CharField(max_length=3500, null=True)),
                ("exclude_columns", models.CharField(max_length=3500, null=True)),
                ("full_refresh", models.BooleanField(default=False)),
                ("ready_to_copy", models.BooleanField(default=False)),
                ("auto_sequence", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("updt_dt_tm", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Milkbasket Metadata Sync",
                "db_table": "metadata_sync",
            },
        ),
    ]
