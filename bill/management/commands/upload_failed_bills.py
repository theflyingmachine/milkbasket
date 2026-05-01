import ast
import re
from datetime import datetime

from django.core.management.base import BaseCommand

from register.models import Bill, Customer
from register.utils import get_mongo_client


class Command(BaseCommand):
    help = "Retry failed Mongo bill metadata uploads by parsing log_milkbasket.log"

    # Supports both formats:
    # 1) ... failed : {<dict>} - Bill Number: MB-...
    # 2) ... failed : {<dict>} - Bill Number: MB-... - Error: ...
    FAILED_UPLOAD_RE = re.compile(
        r"save_bill_to_mongo - MongoDB bill upload failed\s*:\s*(\{.*\})\s*-\s*Bill Number:\s*([^\s]+)(?:\s*-\s*Error:.*)?$"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--log-file",
            default="log_milkbasket.log",
            help="Path to application log file (default: log_milkbasket.log)",
        )

    def handle(self, *args, **options):
        log_file = options["log_file"]
        collection = get_mongo_client()

        total_failed = 0
        parsed_ok = 0
        already_exists = 0
        uploaded = 0
        sql_synced = 0
        sql_created = 0
        parse_errors = 0
        upload_errors = 0

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "save_bill_to_mongo - MongoDB bill upload failed" not in line:
                        continue

                    total_failed += 1
                    match = self.FAILED_UPLOAD_RE.search(line.strip())
                    if not match:
                        parse_errors += 1
                        continue

                    metadata_str, bill_number = match.groups()
                    try:
                        metadata = ast.literal_eval(metadata_str)
                        if not isinstance(metadata, dict):
                            parse_errors += 1
                            continue
                    except (ValueError, SyntaxError):
                        parse_errors += 1
                        continue

                    parsed_ok += 1

                    # Duplicate check in MongoDB using bill_number
                    existing = collection.find_one({"bill_number": bill_number}, {"_id": 1})
                    if existing:
                        already_exists += 1
                        mongo_id = str(existing.get("_id"))
                        sql_created += self._ensure_sql_bill(metadata, bill_number)
                        sql_synced += self._sync_sql_bill_mongo_id(bill_number, mongo_id)
                        continue

                    try:
                        inserted_id = collection.insert_one(metadata).inserted_id
                        uploaded += 1
                        sql_created += self._ensure_sql_bill(metadata, bill_number)
                        sql_synced += self._sync_sql_bill_mongo_id(bill_number, str(inserted_id))
                    except Exception as exc:
                        upload_errors += 1
                        self.stderr.write(
                            self.style.ERROR(
                                f"Failed to upload bill {bill_number} to MongoDB: {exc}"
                            )
                        )

        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"Log file not found: {log_file}"))
            return

        self.stdout.write(self.style.SUCCESS("Upload retry completed."))
        self.stdout.write(f"Failed log entries found: {total_failed}")
        self.stdout.write(f"Successfully parsed entries: {parsed_ok}")
        self.stdout.write(f"Already present in MongoDB: {already_exists}")
        self.stdout.write(f"Uploaded to MongoDB now: {uploaded}")
        self.stdout.write(f"Bill rows created in SQL: {sql_created}")
        self.stdout.write(f"Bill.mongo_id synced in SQL: {sql_synced}")
        self.stdout.write(f"Parse errors: {parse_errors}")
        self.stdout.write(f"Upload errors: {upload_errors}")

    @staticmethod
    def _ensure_sql_bill(metadata, bill_number):
        """Create SQL Bill row if missing, using parsed bill metadata."""
        if Bill.objects.filter(bill_number=bill_number).exists():
            return 0

        customer_id = metadata.get('customer_id')
        if not customer_id:
            return 0
        customer = Customer.objects.filter(id=customer_id).first()
        if not customer:
            return 0

        amount = 0
        bill_summary = metadata.get('bill_summary') or []
        if bill_summary and isinstance(bill_summary[-1], dict):
            amount = bill_summary[-1].get('sum_total') or 0

        last_update = metadata.get('last_update')
        try:
            bill_last_data_date = datetime.strptime(last_update, "%d %B %Y") if last_update else datetime.now()
        except ValueError:
            bill_last_data_date = datetime.now()

        Bill.objects.create(
            customer_id=customer,
            bill_number=bill_number,
            amount=amount,
            bill_last_data_date=bill_last_data_date,
        )
        return 1

    @staticmethod
    def _sync_sql_bill_mongo_id(bill_number, mongo_id):
        bill = Bill.objects.filter(bill_number=bill_number).first()
        if not bill:
            return 0
        if bill.mongo_id == mongo_id:
            return 0
        bill.mongo_id = mongo_id
        bill.save(update_fields=["mongo_id"])
        return 1
