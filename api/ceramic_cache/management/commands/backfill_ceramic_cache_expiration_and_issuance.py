from django.core.management.base import BaseCommand
from django.db import connection
from ceramic_cache.models import CeramicCache


class Command(BaseCommand):
    help = "Backfills expiration_date and issuance_date from JSON data"

    def handle(self, *args, **options):
        batch_size = 10000
        max_id = CeramicCache.objects.latest("id").id
        current_id = 0

        while current_id < max_id:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ceramic_cache_ceramiccache
                    SET
                        expiration_date = (stamp::json->>'expirationDate')::timestamp,
                        issuance_date = (stamp::json->>'issuanceDate')::timestamp
                    WHERE
                        id > %s
                        AND id <= %s
                        AND (expiration_date IS NULL OR issuance_date IS NULL)
                """,
                    [current_id, current_id + batch_size],
                )

            self.stdout.write(
                self.style.SUCCESS(f"Backfilled up to id {current_id + batch_size}")
            )

            current_id += batch_size
            self.stdout.write(f"Processed up to id {current_id}")

        self.stdout.write(self.style.SUCCESS("Data backfill completed successfully"))
