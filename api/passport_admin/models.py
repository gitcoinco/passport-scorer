"""
Module for defining models for Passport Admin.
Includes models for PassportBanner and DismissedBanners.
"""

from django.db import models
from account.models import EthAddressField

APPLICATION_CHOICES = [
    ("passport", "Passport"),
    ("id_staking_v2", "ID Staking V2"),
]


class PassportBanner(models.Model):
    """
    Model representing a Passport Banner.
    """

    content = models.TextField()
    link = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    application = models.CharField(
        max_length=50,
        choices=APPLICATION_CHOICES,
        default="passport",
        db_index=True,
    )


class DismissedBanners(models.Model):
    """
    Model representing Dismissed Banners.
    """

    address = models.CharField(max_length=255)
    banner = models.ForeignKey(
        PassportBanner,
        on_delete=models.CASCADE,
        default=None,
        related_name="dismissedbanners",
    )


# Notifications
NOTIFICATION_TYPES = [
    ("custom", "Custom"),
    ("stamp_expiry", "Stamp Expiry"),
    ("on_chain_expiry", "OnChain Expiry"),
    ("deduplication", "Deduplication"),
]


class Notification(models.Model):
    """
    Model representing a Notification.
    """

    notification_id = models.CharField(
        max_length=255, unique=True
    )  # unique deterministic identifier for the notification

    type = models.CharField(
        max_length=50, choices=NOTIFICATION_TYPES, default="custom", db_index=True
    )
    is_active = models.BooleanField(default=False)

    link = models.CharField(max_length=255, null=True, blank=True)
    link_text = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField()
    created_at = models.DateField(auto_now_add=True)
    expires_at = models.DateField(null=True, blank=True)
    eth_address = EthAddressField(
        null=True, blank=True
    )  # account/ eth address for which the notification is created. If null then it is a global notification wgich will be shown to all users.


class NotificationStatus(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(
        default=False
    )  # is dismissed => should not longer be shown to the user
    eth_address = EthAddressField(
        db_index=True
    )  # The account / eth address that dissmised the notification. Required to track the dismissed notifications / user in case of global notifications.
