import json
import os
import sys
from datetime import datetime
from shutil import rmtree

import oci

from django.apps import apps
from django.db import transaction
from django.db.models import ForeignKey
from django.db.models import ManyToManyField
from django.db.models import Q

from milkbasket.secret import OCI_NAMESPACE, OCI_BUCKET_CONFIG


class MetadataSync:
    @staticmethod
    def topological_sort(meta_tree, models_to_sync):
        """
        Perform a topological sort on the given dependencies to determine the order in which
        models should be exported/imported.
        """
        visited = set()
        stack = []
        dependencies = {
            model_name: set(model_data['dependency'])
            for model_name, model_data in meta_tree.items()
        }

        def dfs(node):
            visited.add(node)
            for neighbor in dependencies.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
            stack.append(node)

        for node in dependencies:
            if node not in visited:
                dfs(node)

        ordered_models = []
        for sorted_model in stack:
            for model in models_to_sync:
                if f'{model.app_name}.{model.model_name}' == sorted_model:
                    ordered_models.append(model)

        return ordered_models

    @staticmethod
    def save_json(data, folder, file_name):
        """Save JSON data to a file."""
        file_path = os.path.join(folder, f'{file_name}.json')
        os.makedirs(folder, exist_ok=True)
        with open(file_path, 'w') as json_file:
            json.dump(data, json_file, indent=4)

    @staticmethod
    def custom_json_serializer(obj):
        """Custom JSON serializer function to handle serialization of non-standard types."""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, (list, tuple)):
            return [MetadataSync.custom_json_serializer(item) for item in obj]
        elif isinstance(obj, dict):
            return {
                str(key): MetadataSync.custom_json_serializer(value) for key, value in obj.items()
            }
        return str(obj)

    @staticmethod
    def serialize_data(queryset, export_pref, model_class):
        """
        Serialize the data from the given queryset. Removes any columns to be excluded based
        on export preferences.
        """
        exclude_column_names = (
            set(col.strip().upper() for col in export_pref.exclude_columns.split(','))
            if export_pref.exclude_columns
            else set()
        )
        dict_res = []
        for qs in queryset.order_by(model_class._meta.pk.name):
            serialized_qs = {
                key: MetadataSync.custom_json_serializer(value)
                for key, value in qs.items()
                if key not in exclude_column_names
            }
            dict_res.append(serialized_qs)

        return dict_res

    @staticmethod
    def filter_data(model_class, export_pref):
        """Filter data from the given model class based on export preferences."""
        filters = json.loads(export_pref.table_filters) if export_pref.table_filters else {}
        queryset = model_class.objects.filter(**filters).values()
        if export_pref.ready_to_copy:
            model_class.objects.filter(**filters).update(ready_to_copy=False)

        return queryset

    @staticmethod
    def get_model_datatypes(model_class):
        """
        Retrieve column data types and related models for the fields of the given model class.
        """
        column_data_types = {}
        dependent_models = []
        for field in model_class._meta.fields:
            column_data_types[field.name] = {'type': field.get_internal_type()}
            if field.get_internal_type() in (
                'ForeignKey',
                'ManyToManyField',
                'OneToOneField',
            ):
                related_model = field.related_model
                column_data_types[field.name]['related_model'] = related_model._meta.object_name
                column_data_types[field.name]['related_app'] = related_model._meta.app_label
                column_data_types[field.name]['field_name'] = field.attname
                dependent_models.append(
                    f'{related_model._meta.app_label}.{related_model._meta.object_name}'
                )

        return column_data_types, dependent_models

    @staticmethod
    def filter_related_data(queryset, parent_querysets):
        """Filter the given queryset based on related data from multiple parent querysets."""
        parent_filters = Q()
        for parent_queryset, condition in parent_querysets:
            for field in queryset.model._meta.get_fields():
                if (
                    isinstance(field, (ForeignKey, ManyToManyField))
                    and field.related_model == parent_queryset.model
                ):
                    parent_ids = parent_queryset.values_list('pk', flat=True)
                    filter_kwargs = {f'{field.name}__in': parent_ids}
                    if condition == 'AND':
                        parent_filters &= Q(**filter_kwargs)
                    elif condition == 'OR':
                        parent_filters |= Q(**filter_kwargs)

        return queryset.filter(parent_filters)

    @classmethod
    def get_meta_tree(cls, all_models):
        """Generate a metadata tree representing the relationships between models."""
        meta_tree = {}
        for app_model in all_models:
            if not app_model.app_name and not app_model.model_name:
                continue
            try:
                model_class = apps.get_model(app_model.app_name, app_model.model_name)
            except LookupError:
                sys.stdout.write(
                    f"Model '{app_model.app_name, app_model.model_name}' not found. Skipping.\n"
                )
                continue
            column_data_types, dependent_models = cls.get_model_datatypes(model_class)
            meta_tree[f'{app_model.app_name}.{app_model.model_name}'] = {
                'dependency': sorted(set(dependent_models)),
                'required_by': [],
                'metadata': column_data_types,
                'model': model_class,
            }
            for model_name, model_data in meta_tree.items():
                for dependency in model_data['dependency']:
                    if (
                        dependency in meta_tree
                        and model_name not in meta_tree[dependency]['required_by']
                    ):
                        meta_tree[dependency]['required_by'].append(model_name)

        return meta_tree

    @classmethod
    def export_json(cls, model, current_model_app, json_data, model_qs_mapper, local_data_dir):
        """Export data for the given model in JSON format."""
        model_class = json_data.pop('model')
        queryset = cls.filter_data(model_class, model)
        if json_data['dependency'] and model.inherit_parent_filter:
            # This model depends on other models, get its parent queryset
            inherit_filters = json.loads(model.inherit_parent_filter)
            parent_qs = [
                (model_qs_mapper[dep], condition)
                for dep, condition in inherit_filters.items()
                if dep in model_qs_mapper and dep != current_model_app
            ]
            queryset = cls.filter_related_data(queryset, parent_qs)

        # Store queryset if model has any dependent model
        if json_data['required_by']:
            model_qs_mapper[current_model_app] = queryset

        json_data['data'] = cls.serialize_data(queryset, model, model_class)
        folder = f'{local_data_dir}/{model.report_name}'
        cls.save_json(json_data, folder, current_model_app)

    @staticmethod
    def read_json_file(json_file):
        """Reads and parses a JSON file."""
        with open(json_file, 'r') as file:
            return json.load(file)

    @staticmethod
    def convert_data_types(json, related_obj):
        """Converts data types in a JSON object according to the metadata and related objects."""
        converted_data, converted_mapping = [], {}
        data, metadata, required_by = json['data'], json['metadata'], json['required_by']
        for item in data:
            for field_name, meta in metadata.items():
                if meta['type'] in ('ForeignKey', 'OneToOneField'):
                    related_field = meta['field_name']
                    try:
                        related_app_model = f"{meta['related_app']}.{meta['related_model']}"
                        item[field_name] = related_obj[related_app_model][item[related_field]]
                    except KeyError:
                        # Parent object does not exist or is not being imported currently,
                        # do not remove existing related field
                        continue
                    item.pop(related_field)
                    converted_mapping[related_field] = field_name

            converted_data.append(item)

        return converted_data, converted_mapping

    @staticmethod
    def clean_table(model_class, export_pref):
        """Cleans the table by deleting rows based on specified filters or truncates it entirely"""
        if export_pref.table_filters:
            filter_criteria = export_pref.table_filters
            model_class.objects.filter(**filter_criteria).delete()
        elif not (
            export_pref.inherit_parent_filter or export_pref.app_name.upper() in ('PREFERENCES')
        ):
            model_class.objects.all().delete()
            # Using Django's ORM to delete all rows may fail due to foreign key constraints.
            # To ensure complete deletion despite constraints, a raw SQL query is utilized
            # to truncate the table.
            # Additional check is implemented to safeguard against unintended truncation
            # of tables due to misconfiguration. These checks particularly focus on Preference
            # tables as a fail-safe measure.
            # schema = 'reports' if export_pref.report_name == 'SLA_DBA' else 'default'
            # with connections[schema].cursor() as cursor:
            #     table_name = model_class._meta.db_table.split('.')[-1].strip('"')
            #     truncate_query = f'TRUNCATE TABLE {table_name}'
            #     cursor.execute(truncate_query)

    @staticmethod
    def prepare_update_on(row, table_update_on, converted_mapping):
        """Prepares update criteria for a row based on specified table update columns and
        converted field mapping."""
        update_criteria = {}
        if table_update_on:
            update_cols = table_update_on.split(',')
            for col in update_cols:
                col = converted_mapping.get(col) if col in converted_mapping.keys() else col
                update_criteria[col.strip()] = row.pop(col.strip())

        return update_criteria, row

    @classmethod
    @transaction.atomic
    def import_json(cls, model, current_model_app, meta_tree, model_qs_mapper, local_data_dir):
        """Imports JSON data into the database for a specific model."""
        model_class = meta_tree[current_model_app].pop('model')
        json_file = os.path.join(local_data_dir, model.report_name, f'{current_model_app}.json')
        json_data = cls.read_json_file(json_file)
        converted_data, converted_mapping = cls.convert_data_types(json_data, model_qs_mapper)

        if not converted_data:
            return "No records to import"

        if model.full_refresh or not model.table_update_on:
            cls.clean_table(model_class, model)
            objects_to_create = [model_class(**item) for item in converted_data]
            created = model_class.objects.bulk_create(objects_to_create, batch_size=500)
            return f'{len(created)} records created'

        else:
            created_rows, updated_rows = 0, 0
            pk = model_class._meta.pk.name
            # breakpoint()
            for row in converted_data:
                update_on_cols, default_data = cls.prepare_update_on(
                    row, model.table_update_on, converted_mapping
                )
                # Remove the PK if auto_seq_ind is set, and let the database create new id
                try:
                    json_id = default_data.pop(pk) if model.auto_sequence else default_data[pk]
                except KeyError:
                    json_id = update_on_cols[pk]

                obj, created = model_class.objects.update_or_create(
                    **update_on_cols,
                    defaults=default_data,
                )
                if created:
                    created_rows += 1
                else:
                    updated_rows += 1

                if json_data['required_by']:
                    model_qs_mapper[current_model_app][json_id] = obj

            return f'{created_rows} rows created, {updated_rows} rows updated'


class ObjectStore:
    def __init__(self, local_data_dir, bucket_name):
        self.namespace_name = OCI_NAMESPACE
        self.bucket_name = bucket_name
        self.local_data_dir = local_data_dir
        self.object_storage = oci.object_storage.ObjectStorageClient(
            OCI_BUCKET_CONFIG
        )

    def upload_file_to_object_storage(self, item, parent_folder=''):
        """Uploads a file to object storage under an optional parent folder."""
        item_path = os.path.join(self.local_data_dir, item)
        object_name = os.path.join(parent_folder, item) if parent_folder else item
        with open(item_path, 'rb') as file:
            self.object_storage.put_object(
                self.namespace_name, self.bucket_name, object_name, file
            )

    def download_object_from_object_storage(self, object_name, local_path):
        """Downloads an object from the object storage to the specified local path."""
        response = self.object_storage.get_object(
            self.namespace_name, self.bucket_name, object_name
        )
        with open(local_path, 'wb') as f:
            for chunk in response.data.raw.stream(1024 * 1024, decode_content=False):
                f.write(chunk)

    def download_folder_from_object_storage(self, folder):
        """Downloads folder and its contents from the object store to the local data directory."""
        if os.path.exists(folder):
            rmtree(self.local_data_dir)
        for obj in self.object_storage.list_objects(
            self.namespace_name, self.bucket_name, prefix=folder
        ).data.objects:
            if obj.name.endswith('/'):
                continue
            local_file = obj.name.replace(folder + '/', '')
            local_path = os.path.join(self.local_data_dir, local_file)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.download_object_from_object_storage(obj.name, local_path)

    def get_file_content_from_object_storage(self, object_path):
        """Retrieves the binary content of a file from object storage by object name with path.
        Reruns None if file doesn't exist."""
        try:
            response = self.object_storage.get_object(
                self.namespace_name, self.bucket_name, object_path
            )
        except oci.exceptions.ServiceError as e:
            if e.status == 404:
                return None
            raise e
        return response.data.content

