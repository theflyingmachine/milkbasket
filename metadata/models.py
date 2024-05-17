from django.db import models


class MBMetadataSync(models.Model):
    """
    Stores the list of models to be exported/imported with required configuration parameters for
    syncing metadata
    """

    id = models.AutoField(primary_key=True)
    report_name = models.CharField(max_length=500)
    app_name = models.CharField(max_length=500)
    model_name = models.CharField(max_length=500)
    db_table = models.CharField(max_length=500)
    table_filters = models.CharField(max_length=3500, null=True)
    table_update_on = models.CharField(max_length=3500, null=True)
    inherit_parent_filter = models.CharField(max_length=3500, null=True)
    exclude_columns = models.CharField(max_length=3500, null=True)
    full_refresh = models.BooleanField(default=False)
    ready_to_copy = models.BooleanField(default=False)
    auto_sequence = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    updt_dt_tm = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'metadata_sync'
        verbose_name = 'Milkbasket Metadata Sync'