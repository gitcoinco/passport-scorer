"""Ceramic Cache Models"""

from enum import IntEnum

from account.models import EthAddressField
from django.db import models
from django.db.models import Q, UniqueConstraint


class CeramicCache(models.Model):
    class StampType(IntEnum):
        V1 = 1
        V2 = 2

    class ComposeDBSaveStatus(models.TextChoices):
        PENDING = "pending"
        SAVED = "saved"
        FAILED = "failed"

    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict)
    created_at = models.DateTimeField(
        auto_now_add=True,
        blank=True,
        null=True,
        help_text="This is the timestamp that this DB record was created (it is not necessarily the stamp issuance timestamp)",
    )

    # NOTE! auto_now is here to make tests easier, but it is not
    # supported for bulk updates so it should be set explicitly
    updated_at = models.DateTimeField(
        blank=False,
        null=False,
        auto_now=True,
        help_text="This is the timestamp that this DB record was updated (it is not necessarily the stamp issuance timestamp)",
    )

    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="This is the timestamp that this DB record was deleted",
    )

    type = models.IntegerField(
        default=StampType.V1,
        choices=[(tag.value, tag.name) for tag in StampType],
        help_text="TO BE DELETED - this is not used",
    )

    compose_db_save_status = models.CharField(
        max_length=10,
        choices=ComposeDBSaveStatus.choices,
        default="",
        blank=True,
        db_index=True,
    )

    compose_db_stream_id = models.CharField(
        max_length=100,
        default="",
        blank=True,
        help_text="Compose db stream ID for CREDENTIAL WRAPPER",
        db_index=True,
    )

    issuance_date = models.DateTimeField(
        null=True, db_index=True
    )  # stamp['issuanceDate']
    expiration_date = models.DateTimeField(
        null=True, db_index=True
    )  # stamp['expirationDate']

    class Meta:
        unique_together = ["type", "address", "provider", "deleted_at"]

        constraints = [
            # UniqueConstraint for non-deleted records
            UniqueConstraint(
                fields=["type", "address", "provider"],
                name="unique_non_deleted_provider_for_address",
                condition=Q(deleted_at__isnull=True),
            ),
            # UniqueConstraint for deleted records
            UniqueConstraint(
                fields=["type", "address", "provider", "deleted_at"],
                name="unique_deleted_provider_for_address",
                condition=Q(deleted_at__isnull=False),
            ),
        ]


class StampExports(models.Model):
    last_export_ts = models.DateTimeField(auto_now_add=True)
    stamp_total = models.IntegerField(default=0)


class CeramicCacheLegacy(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    stamp = models.JSONField(default=dict, db_index=True)

    class Meta:
        unique_together = ["address", "provider"]
