import pytest
import dag_cbor
import hashlib
from django.test import Client
from django.utils import timezone
from datetime import timedelta
from ceramic_cache.api.v1 import DbCacheToken
from registry.models import Event
from collections import Counter
from ceramic_cache.models import CeramicCache
from passport_admin.models import Notification, NotificationStatus

pytestmark = pytest.mark.django_db

client = Client()


@pytest.fixture
def sample_address():
    return "0xc79abb54e4824cdb65c71f2eeb2d7f2db5da1fb8"


@pytest.fixture
def sample_token(sample_address):
    token = DbCacheToken()
    token["token_type"] = "access"
    token["did"] = f"did:pkh:eip155:1:{sample_address.lower()}"

    return str(token)


@pytest.fixture
def current_date():
    return timezone.now().date()


@pytest.fixture
def custom_notifications(current_date, sample_address):
    ret = {
        "active": Notification.objects.create(
            notification_id="custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "inactive": Notification.objects.create(
            notification_id="custom_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "expired": Notification.objects.create(
            notification_id="expired_custom_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
            eth_address=sample_address,
        ),
        "read": Notification.objects.create(
            notification_id="custom_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
        "deleted": Notification.objects.create(
            notification_id="custom_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a custom notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
            eth_address=sample_address,
        ),
    }

    NotificationStatus.objects.create(
        notification=ret["read"],
        is_read=True,
        eth_address=sample_address,
    )

    NotificationStatus.objects.create(
        notification=ret["deleted"],
        is_deleted=True,
        eth_address=sample_address,
    )

    return ret


@pytest.fixture
def generic_notifications(current_date, sample_address):
    ret = {
        "active": Notification.objects.create(
            notification_id="generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "inactive": Notification.objects.create(
            notification_id="generic_inactive",
            type="custom",
            is_active=False,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=1)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "expired": Notification.objects.create(
            notification_id="expired_generic_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date - timedelta(days=1)),
        ),
        "read": Notification.objects.create(
            notification_id="generic_read_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
        ),
        "deleted": Notification.objects.create(
            notification_id="generic_deleted_active",
            type="custom",
            is_active=True,
            content="Hello! This is a generic notification",
            created_at=(current_date - timedelta(days=3)),
            expires_at=(current_date + timedelta(days=1)),
        ),
    }

    read = NotificationStatus.objects.create(
        notification=ret["read"],
        is_read=True,
        eth_address=sample_address,
    )
    print("read is read", read.is_read)

    NotificationStatus.objects.create(
        notification=ret["deleted"],
        is_deleted=True,
        eth_address=sample_address,
    )

    return ret


@pytest.fixture
def deduplication_event(sample_address):
    event = Event.objects.create(
        action=Event.Action.LIFO_DEDUPLICATION,
        address=sample_address,
        data={
            "hash": "some_hash",
            "provider": "some_provider",
            "community_id": "some_community_id",
        },
    )
    return event


@pytest.fixture
def expired_stamp(sample_address):
    cc_expired = CeramicCache.objects.create(
        address=sample_address,
        provider="some_provider",
        created_at=timezone.now() - timedelta(days=3),
        stamp={"credentialSubject": {"hash": "some_hash", "id": "some_id"}},
        expiration_date=timezone.now() + timedelta(days=30),
        issuance_date=timezone.now() - timedelta(days=3),
    )

    cc_deleted = CeramicCache.objects.create(
        address=sample_address,
        provider="some_provider",
        deleted_at=timezone.now(),
        created_at=timezone.now() - timedelta(days=3),
        stamp={"credentialSubject": {"hash": "some_hash", "id": "some_id"}},
        expiration_date=timezone.now() + timedelta(days=30),
        issuance_date=timezone.now() - timedelta(days=3),
    )

    return cc_expired


# TODO: test when a notification already exists
class TestNotifications:
    # def test_get_address(self, sample_address, sample_token):
    #     assert get_address(sample_token) == sample_address

    def test_get_active_notifications_for_address(
        self,
        sample_token,
        sample_address,
        custom_notifications,
        generic_notifications,
        deduplication_event,
        expired_stamp,
    ):
        response = client.post(
            "/passport-admin/notifications",
            {},
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_deduplication_notification = {
            "notification_id": hashlib.sha256(
                dag_cbor.encode(
                    {
                        "action": deduplication_event.action,
                        "address": deduplication_event.address,
                        "data": deduplication_event.data,
                        "id": deduplication_event.id,
                    }
                )
            ).hexdigest(),
            "type": "deduplication",
            "link": "https://github.com/orgs/gitcoinco/projects/6/views/link",
            "link_text": "here",
            "content": f"You have claimed the same `{deduplication_event.data['provider']}` stamp in two Passports. We only count your stamp once. This duplicate is in your wallet {sample_address}. Learn more about deduplication",
            "is_read": False,
        }

        expected_expired_stamp_notification = {
            "notification_id": hashlib.sha256(
                dag_cbor.encode(
                    {
                        "cc_id": expired_stamp.id,
                        "cc_provider": expired_stamp.provider,
                        "cc_stamp_hash": expired_stamp.stamp["credentialSubject"][
                            "hash"
                        ],
                        "cc_stamp_id": expired_stamp.stamp["credentialSubject"]["id"],
                        "address": sample_address,
                    }
                )
            ).hexdigest(),
            "type": "stamp_expiry",
            "link": None,
            "link_text": None,
            "content": f"Your {expired_stamp.provider} stamp has expired. Please reverify to keep your Passport up to date.",
            "is_read": False,
        }

        expected_response = {
            "items": [
                {
                    "notification_id": custom_notifications["active"].notification_id,
                    "type": custom_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["active"].content,
                    "is_read": False,
                },
                {
                    "notification_id": custom_notifications["read"].notification_id,
                    "type": custom_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": custom_notifications["read"].content,
                    "is_read": True,
                },
                {
                    "notification_id": generic_notifications["active"].notification_id,
                    "type": generic_notifications["active"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["active"].content,
                    "is_read": False,
                },
                {
                    "notification_id": generic_notifications["read"].notification_id,
                    "type": generic_notifications["read"].type,
                    "link": None,
                    "link_text": None,
                    "content": generic_notifications["read"].content,
                    "is_read": True,
                },
                expected_deduplication_notification,
                expected_expired_stamp_notification,
            ]
        }

        res = response.json()
        assert Counter(map(frozenset, res["items"])) == Counter(
            map(frozenset, expected_response["items"])
        )

    def test_expired_chain(self, sample_token, sample_address):
        response = client.post(
            "/passport-admin/notifications",
            {
                "expired_chain_ids": [
                    {"id": "chain1", "name": "Chain 1"},
                    {"id": "chain2", "name": "Chain 2"},
                ]
            },
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
            content_type="application/json",
        )

        expected_response = {
            "items": [
                {
                    "notification_id": hashlib.sha256(
                        dag_cbor.encode(
                            {
                                "chain_id": "chain1",
                                "chain_name": "Chain 1",
                                "address": sample_address,
                            }
                        )
                    ).hexdigest(),
                    "type": "on_chain_expiry",
                    "link": None,
                    "link_text": None,
                    "content": "Your on-chain Passport on Chain 1 has expired. Update now to maintain your active status.",
                    "is_read": False,
                },
                {
                    "notification_id": hashlib.sha256(
                        dag_cbor.encode(
                            {
                                "chain_id": "chain2",
                                "chain_name": "Chain 2",
                                "address": sample_address,
                            }
                        )
                    ).hexdigest(),
                    "type": "on_chain_expiry",
                    "link": None,
                    "link_text": None,
                    "content": "Your on-chain Passport on Chain 2 has expired. Update now to maintain your active status.",
                    "is_read": False,
                },
            ]
        }
        res = response.json()
        assert Counter(map(frozenset, res["items"])) == Counter(
            map(frozenset, expected_response["items"])
        )

    def test_read_notification(
        self, sample_token, sample_address, custom_notifications
    ):
        notification_id = custom_notifications["active"].notification_id
        response = client.post(
            f"/passport-admin/notifications/{notification_id}",
            {
                "dismissal_type": "read",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        read_notification = NotificationStatus.objects.get(
            notification=custom_notifications["active"],
            is_read=True,
            eth_address=sample_address,
        )
        assert read_notification.is_read is True
        assert read_notification.eth_address == sample_address

    def test_delete_notification(
        self, sample_token, sample_address, custom_notifications
    ):
        notification_id = custom_notifications["active"].notification_id
        response = client.post(
            f"/passport-admin/notifications/{notification_id}",
            {
                "dismissal_type": "delete",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "success"}

        deleted_notification = NotificationStatus.objects.get(
            notification=custom_notifications["active"],
            is_deleted=True,
            eth_address=sample_address,
        )
        assert deleted_notification.is_deleted is True
        assert deleted_notification.is_read is False
        assert deleted_notification.eth_address == sample_address

    def test_dismiss_notification_invalid_id(self, sample_token):
        response = client.post(
            "/passport-admin/notifications/invalid_id",
            {
                "dismissal_type": "read",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {sample_token}",
        )

        assert response.json() == {"status": "failed"}
