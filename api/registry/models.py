from enum import Enum

from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from account.models import Community, EthAddressField


class Passport(models.Model):
    address = EthAddressField(null=True, blank=False, max_length=100, db_index=True)
    community = models.ForeignKey(
        Community, related_name="passports", on_delete=models.CASCADE, null=True
    )
    requires_calculation = models.BooleanField(
        null=True,
        help_text="This flag indicates that this passport requires calculation of the score. The score calculation task shall skip calculation unless this flag is set.",
    )

    class Meta:
        unique_together = ["address", "community"]

    def __str__(self):
        return f"Passport #{self.id}, address={self.address}, community_id={self.community_id}"


class Stamp(models.Model):
    passport = models.ForeignKey(
        Passport,
        related_name="stamps",
        on_delete=models.CASCADE,
        null=True,
        db_index=True,
    )
    hash = models.CharField(null=False, blank=False, max_length=100, db_index=True)
    provider = models.CharField(
        null=False, blank=False, default="", max_length=256, db_index=True
    )
    credential = models.JSONField(default=dict)

    def __str__(self):
        return f"Stamp #{self.id}, hash={self.hash}, provider={self.provider}, passport={self.passport_id}"

    class Meta:
        unique_together = ["hash", "passport"]


class Score(models.Model):
    class Meta:
        permissions = [("rescore_individual_score", "Can rescore individual scores")]

    class Status:
        PROCESSING = "PROCESSING"
        BULK_PROCESSING = "BULK_PROCESSING"
        DONE = "DONE"
        ERROR = "ERROR"

    STATUS_CHOICES = [
        (Status.PROCESSING, Status.PROCESSING),
        (Status.BULK_PROCESSING, Status.BULK_PROCESSING),
        (Status.DONE, Status.DONE),
        (Status.ERROR, Status.ERROR),
    ]

    passport = models.ForeignKey(
        Passport, on_delete=models.PROTECT, related_name="score", unique=True
    )
    score = models.DecimalField(null=True, blank=True, decimal_places=9, max_digits=18)
    last_score_timestamp = models.DateTimeField(
        default=None, null=True, blank=True, db_index=True
    )
    status = models.CharField(
        choices=STATUS_CHOICES, max_length=20, null=True, default=None, db_index=True
    )
    error = models.TextField(null=True, blank=True)
    evidence = models.JSONField(null=True, blank=True)
    stamp_scores = models.JSONField(null=True, blank=True)

    expiration_date = models.DateTimeField(
        default=None, null=True, blank=True, db_index=True
    )

    def __str__(self):
        return f"Score #{self.id}, score={self.score}, last_score_timestamp={self.last_score_timestamp}, status={self.status}, error={self.error}, evidence={self.evidence}, passport_id={self.passport_id}"


@receiver(pre_save, sender=Score)
def score_updated(sender, instance, **kwargs):
    if instance.status != Score.Status.DONE:
        return instance

    Event.objects.create(
        action=Event.Action.SCORE_UPDATE,
        address=instance.passport.address,
        community=instance.passport.community,
        data={
            "score": float(instance.score) if instance.score is not None else 0,
            "evidence": instance.evidence,
        },
    )

    return instance


class Event(models.Model):
    # Example usage:
    #   obj.action = Event.Action.FIFO_DEDUPLICATION
    class Action(models.TextChoices):
        FIFO_DEDUPLICATION = "FDP"
        LIFO_DEDUPLICATION = "LDP"
        TRUSTALAB_SCORE = "TLS"
        SCORE_UPDATE = "SCU"

    action = models.CharField(
        max_length=3,
        choices=Action.choices,
        blank=False,
    )

    address = EthAddressField(
        blank=True,
        max_length=42,
    )

    ########################################################################################
    # BEGIN: section containing fields that are only used for certain actions
    # and will be set to None otherwise
    ########################################################################################
    community = models.ForeignKey(
        Community,
        on_delete=models.PROTECT,
        related_name="event",
        null=True,
        default=None,
        help_text="""
This field is only used for the SCORE_UPDATE and Deduplication events.
The reason to have this field (and not use the `data` JSON field) is to be able to easily have an index for the community_id for faster lookups.
""",
    )
    ########################################################################################
    # END: section with action - specific fields
    ########################################################################################

    created_at = models.DateTimeField(auto_now_add=True)

    data = models.JSONField()

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "action",
                    "address",
                    "community",
                    "created_at",
                ],
                name="score_history_index",
            ),
        ]


class HashScorerLink(models.Model):
    hash = models.CharField(null=False, blank=False, max_length=100, db_index=True)
    community = models.ForeignKey(
        Community,
        related_name="burned_hashes",
        on_delete=models.CASCADE,
        null=False,
        db_index=True,
    )
    address = EthAddressField(null=False, blank=False, db_index=True)
    expires_at = models.DateTimeField(null=False, blank=False, db_index=True)

    class Meta:
        unique_together = ["hash", "community"]


# For the legacy GTC staking events
class GTCStakeEvent(models.Model):
    event_type = models.CharField(max_length=15)
    round_id = models.IntegerField(db_index=True)
    staker = EthAddressField(blank=False, db_index=True)
    address = EthAddressField(null=True, blank=False, db_index=True)
    amount = models.DecimalField(max_digits=78, decimal_places=18)
    staked = models.BooleanField()
    block_number = models.IntegerField()
    tx_hash = models.CharField(max_length=66)

    class Meta:
        indexes = [
            models.Index(
                fields=["round_id", "address", "staker"],
                name="gtc_staking_index",
            ),
            models.Index(
                fields=["round_id", "staker"],
                name="gtc_staking_index_by_staker",
            ),
        ]


class BatchRequestStatus(str, Enum):
    PENDING = "PENDING"
    DONE = "DONE"
    ERROR = "ERROR"

    def __str__(self):
        return f"{self.value}"


class BatchModelScoringRequest(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    s3_filename = models.CharField(max_length=100, null=False, blank=False)
    model_list = models.CharField(max_length=100, null=False, blank=False)
    status = models.CharField(
        max_length=10,
        choices=[(status.value, status) for status in BatchRequestStatus],
        default=BatchRequestStatus.PENDING,
    )
    progress = models.IntegerField(default=0, help_text="Progress in percentage: 0-100")
