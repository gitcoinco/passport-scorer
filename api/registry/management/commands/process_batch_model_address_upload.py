import asyncio
import csv
from io import BytesIO, StringIO, TextIOWrapper
from itertools import islice

import boto3
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from tqdm import tqdm

from passport.api import fetch_all, handle_get_analysis
from registry.admin import get_s3_client
from registry.models import BatchModelScoringRequest, BatchRequestStatus
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)


class Command(BaseCommand):
    help = "Process batch model address uploads"

    def handle(self, *args, **options):
        asyncio.run(self.async_handle(*args, **options))

    async def async_handle(self, *args, **options):
        pending_requests = await sync_to_async(list)(
            BatchModelScoringRequest.objects.filter(
                status=BatchRequestStatus.PENDING.value
            )
        )

        for request in pending_requests:
            try:
                self.stdout.write(f"Processing request: {request.id}")

                file = await sync_to_async(self.download_from_s3)(request.s3_filename)

                if file:
                    self.stdout.write(self.style.SUCCESS("Got stream, processing CSV"))
                    bytes = BytesIO(file.read())
                    text = TextIOWrapper(bytes, encoding="utf-8")
                    csv_data = csv.reader(text)
                    total_rows = sum(1 for row in csv_data)

                    text.seek(0)
                    csv_data = csv.reader(text)

                    model_list = request.model_list

                    results = []
                    processed_rows = 0
                    for batch in self.process_csv_in_batches(csv_data):
                        batch_results = await self.get_analysis(batch, model_list)
                        results.extend(batch_results)
                        processed_rows += len(batch_results)
                        progress = int((processed_rows / total_rows) * 100)
                        await self.update_progress(request, progress)

                    await self.create_and_upload_results_csv(
                        request.id, results, request.s3_filename
                    )

                # Update status to COMPLETED
                request.status = BatchRequestStatus.DONE
                request.progress = 100
                await sync_to_async(request.save)()

                self.stdout.write(
                    self.style.SUCCESS(f"Successfully processed request: {request.id}")
                )
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error processing request {request.id}: {str(e)}")
                )
                # Optionally, update status to ERROR
                request.status = BatchRequestStatus.ERROR
                await sync_to_async(request.save)()

    async def update_progress(self, request, progress):
        request.progress = progress
        await sync_to_async(request.save)()
        self.stdout.write(f"Updated progress for request {request.id}: {progress}%")

    def download_from_s3(self, s3_filename):
        try:
            response = get_s3_client().get_object(
                Bucket=BULK_SCORE_REQUESTS_BUCKET_NAME,
                Key=f"{BULK_SCORE_REQUESTS_ADDRESS_LIST_FOLDER}/{s3_filename}",
            )
            return response["Body"]
        except Exception as e:
            raise CommandError(f"Failed to download file from S3: {str(e)}")

    def process_csv_in_batches(self, csv_data, batch_size=5):
        while True:
            batch = list(islice(csv_data, batch_size))
            if not batch:
                break
            yield batch

    async def get_analysis(self, batch, model_list):
        tasks = []
        for row in batch:
            address = row[0]
            if not address or address == "":
                continue
            task = asyncio.create_task(self.process_address(address, model_list))
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

    async def process_address(self, address, model_list):
        try:
            result = await handle_get_analysis(address, model_list, False)
            return address, result
        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error processing address {address}: {str(e)}")
            )
            return address, None

    async def create_and_upload_results_csv(self, request_id, results, filename):
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["Address", "Result"])  # Header row
        for address, result in results:
            csv_writer.writerow([address, result])

        # Upload to S3
        s3_client = get_s3_client()
        await sync_to_async(s3_client.put_object)(
            Bucket=BULK_SCORE_REQUESTS_BUCKET_NAME,
            Key=f"{BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{filename}",
            Body=csv_buffer.getvalue().encode("utf-8"),
            ContentType="text/csv",
        )
        self.stdout.write(self.style.SUCCESS(f"Uploaded results to S3: {filename}"))
