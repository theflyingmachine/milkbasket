"""
Script to export site metadata to JSON files and push over to bucket, and import JSON
metadata from Object Store bucket to the database.

Configuration Table: METADATA_SYNC
Example Usage:
- Export metadata:
    python manage.py metadata_sync --export
    python manage.py metadata_sync --export --push none
- Import metadata:
    python manage.py metadata_sync --import
    python manage.py metadata_sync --import --pull bucket_production
"""
import argparse
import sys
from datetime import datetime

from django.core.management.base import BaseCommand

from metadata.models import MBMetadataSync
from metadata.utils import MetadataSync
from metadata.utils import ObjectStore
from milkbasket.secret import RUN_ENVIRONMENT

BUCKET_NAME = 'MilkBasket-bucket'
LOCAL_DATA_DIR = 'metadata/local_data'


class Command(BaseCommand):
    help = """
        This management command exports site metadata to JSON files and imports data from JSON 
        files to the database.

        Usage:
             metadata_sync [(--import | --export)] [--push (bucket | none)]
    
        Options:
            -e, --export   Exports metadata from the database to JSON files.
            -i, --import   Imports data from JSON files to the database.
                       (either --export or --import is required)
    
            --push     (optional) Specifies if the exported JSON files should be pushed. 
                            If not specified defaults to 'bucket'
                            bucket: Pushes exported data to Object Store bucket.                           
                            none: Only generates JSON files locally without pushing.
                            
            --pull     (optional) Specifies the <location>_<branch> to import data.
                            Can only be used with --import. Defaults to 'bucket_<ENV>'
        """

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-e', '--export', action='store_true', help='Flag to indicate exporting data'
        )
        group.add_argument(
            '-i', '--import', action='store_true', help='Flag to indicate importing data'
        )
        parser.add_argument(
            '--push',
            choices=['bucket', 'none'],
            default='bucket',
            required=False,
            help='Push to perform: bucket or none',
        )
        parser.add_argument(
            "--pull",
            type=str,
            default=f"bucket_{RUN_ENVIRONMENT}",
            required=False,
            help="Specify the location to import files from bucket folder",
        )


    def handle(self, *args, **options):

        start_time = datetime.now()
        bucket = ObjectStore(LOCAL_DATA_DIR, BUCKET_NAME)
        all_models = MBMetadataSync.objects.all()
        meta_tree = MetadataSync.get_meta_tree(all_models)
        models_to_process = MetadataSync.topological_sort(
            meta_tree, all_models.filter(is_active=True)
        )
        model_qs_mapper = {}
        files_to_upload = []
        count, total = 0, len(models_to_process)
        if options['import']:
            location, branch = options['pull'].split('_')
            bucket.download_folder_from_object_storage(folder=branch)


        for model in models_to_process:
            count += 1
            current_model_app = f'{model.app_name}.{model.model_name}'
            sys.stdout.write(f'({count}/{total}) {current_model_app}...')
            if options['export']:
                MetadataSync.export_json(
                    model,
                    current_model_app,
                    meta_tree[current_model_app],
                    model_qs_mapper,
                    LOCAL_DATA_DIR,
                )
                files_to_upload.append(f'{model.report_name}/{current_model_app}.json')
                self.stdout.write('Done')

            elif options['import']:
                model_qs_mapper[current_model_app] = {}
                status = MetadataSync.import_json(
                    model,
                    current_model_app,
                    meta_tree,
                    model_qs_mapper,
                    LOCAL_DATA_DIR,
                )
                self.stdout.write(status)

        if options['push'] == 'bucket' and options['export']:
            self.stdout.write('Uploading files to Bucket...')
            for file in files_to_upload:
                bucket.upload_file_to_object_storage(file, RUN_ENVIRONMENT)

        self.stdout.write(
            self.style.SUCCESS(
                f"Data {'exported' if options['export'] else 'imported'} successfully!"
            )
        )
        self.stdout.write(f'Completed in {(datetime.now() - start_time).total_seconds()} seconds')
