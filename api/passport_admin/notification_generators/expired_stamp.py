import dag_cbor
import hashlib

from django.utils import timezone
from ceramic_cache.models import CeramicCache
from passport_admin.models import Notification


def generate_stamp_expired_notifications(address):
    """
    Generate stamp expired notifications for a specific address
    """
    current_date = timezone.now().date()

    ceramic_cache = CeramicCache.objects.filter(
        address=address, deleted_at__isnull=True, expiration_date__lt=current_date
    )

    for cc in ceramic_cache:
        encoded_data = dag_cbor.encode(
            {
                "cc_id": cc.id,
                "cc_provider": cc.provider,
                "cc_stamp_hash": cc.stamp["credentialSubject"]["hash"],
                "cc_stamp_id": cc.stamp["credentialSubject"]["id"],
                "address": address,
            }
        )
        notification_id = hashlib.sha256(encoded_data).hexdigest()

        notification_exists = Notification.objects.filter(
            notification_id=notification_id
        ).exists()

        if not notification_exists:
            Notification.objects.create(
                notification_id=notification_id,
                type="stamp_expiry",
                is_active=True,
                content=f"Your {cc.provider} stamp has expired. Please reverify to keep your Passport up to date.",
                link=cc.provider,
            )
