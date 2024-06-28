"""
Module for administering Passport Admin.
This includes registering the relevant models for PassportBanner and DismissedBanners.
"""

from django.contrib import admin

from .models import (
    DismissedBanners,
    PassportBanner,
    Notification,
    NotificationStatus,
)

admin.site.register(DismissedBanners)
admin.site.register(NotificationStatus)


@admin.register(PassportBanner)
class PassportAdmin(admin.ModelAdmin):
    """
    Admin class for PassportBanner.
    """

    list_display = ("content", "link", "is_active", "application")
    search_fields = ("content", "is_active", "link")
    list_filter = ("is_active", "application")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """
    Admin class for Notification.
    """

    list_display = ("notification_id", "type", "is_active", "eth_address")
    search_fields = ("eth_address", "type")
    list_filter = (
        "type",
        "eth_address",
        "is_active",
        "created_at",
        "expires_at",
        "link",
        "link_text",
    )
