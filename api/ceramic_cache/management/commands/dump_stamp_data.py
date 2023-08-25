import datetime
import json
import os

import boto3
from ceramic_cache.models import CeramicCache, StampExports
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.utils import timezone

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.S3_DATA_AWS_SECRET_KEY_ID,
    aws_secret_access_key=settings.S3_DATA_AWS_SECRET_ACCESS_KEY,
)


class Command(BaseCommand):
    help = "Weekly data dump of new Stamp data since the last dump."

    def handle(self, *args, **options):
        print("Starting dump_stamp_data.py")
        latest_export = StampExports.objects.order_by("-last_export_ts").first()
        latest_export_ts = (
            latest_export.last_export_ts
            if latest_export
            else timezone.now() - datetime.timedelta(days=45)
        )

        print(f"Getting data from {latest_export_ts}")

        paginator = Paginator(
            CeramicCache.objects.filter(created_at__gt=latest_export_ts).values_list(
                "stamp", flat=True
            ),
            1000,
        )

        # Generate the dump file name
        file_name = f'stamps_{latest_export_ts.strftime("%Y%m%d_%H%M%S")}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.jsonl'

        # Write serialized data to the file
        with open(file_name, "w") as f:
            for page in paginator.page_range:
                for stamp in paginator.page(page).object_list:
                    f.write(json.dumps({"stamp": stamp}) + "\n")

        # Upload to S3 bucket
        s3.upload_file(file_name, settings.S3_WEEKLY_BACKUP_BUCKET_NAME, file_name)

        # Delete local file after upload
        os.remove(file_name)

        StampExports.objects.create(
            last_export_ts=timezone.now(), stamp_total=paginator.count
        )

        print(f"Data dump completed and uploaded to S3 as {file_name}")
