import dag_cbor
import hashlib

from typing import List
from passport_admin.schema import ChainSchema
from passport_admin.models import Notification


def generate_on_chain_expired_notifications(address, expired_chains: List[ChainSchema]):
    """
    Generate on chain expired notifications for a specific address
    """
    for chain in expired_chains:
        encoded_data = dag_cbor.encode(
            {
                "chain_id": chain.id,
                "chain_name": chain.name,
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
                type="on_chain_expiry",
                is_active=True,
                content=f"Your on-chain Passport on {chain.name} has expired. Update now to maintain your active status.",
            )
