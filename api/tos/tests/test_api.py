import json

import pytest
from django.conf import settings
from django.test import Client
from eth_account.account import Account
from eth_account.messages import encode_defunct
from tos.models import Tos, TosAcceptanceProof

pytestmark = pytest.mark.django_db

client = Client()


class TestTos:
    """
    This will test the API functions that are exposed in the ceramic-cache app.
    """

    def test_check_tos_accepted_when_no_tos_exists(self, sample_token):
        """Test that accepted is not confirmed when tos does not exist."""

        client = Client()

        tos_check_response = client.get(
            f"/ceramic-cache/tos/accepted/{Tos.TosType.IDENTITY_STAKING}/0x1",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert tos_check_response.status_code == 200
        assert tos_check_response.json() == {
            "accepted": False,
        }

    def test_check_tos_accepted_when_no_tos_is_accepted(self, sample_token):
        """Test that accepted is not confirmed when it is not."""

        Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING, active=True, content="Hello World !!!"
        )

        client = Client()

        tos_check_response = client.get(
            f"/ceramic-cache/tos/accepted/{Tos.TosType.IDENTITY_STAKING}/0x1",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert tos_check_response.status_code == 200
        assert tos_check_response.json() == {
            "accepted": False,
        }

    def test_check_tos_accepted(self, sample_token):
        """Test that accepted is not confirmed."""

        tos = Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING, active=True, content="Hello World !!!"
        )

        TosAcceptanceProof.objects.create(
            tos=tos, address="0x1", nonce="abc", signature="0x1234"
        )

        client = Client()

        tos_check_response = client.get(
            f"/ceramic-cache/tos/accepted/{Tos.TosType.IDENTITY_STAKING}/0x1",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert tos_check_response.status_code == 200
        assert tos_check_response.json() == {
            "accepted": True,
        }

    def test_get_check_to_sign(self, sample_token):
        """Test that tos to sign is returned."""

        # Create multiple tos, but we only check for the active one in the end
        Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING,
            active=True,
            final=True,
            content="Hello World !!!",
        )

        Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING,
            active=False,
            content="Old Hello World !!!",
        )

        client = Client()

        tos_check_response = client.get(
            f"/ceramic-cache/tos/message-to-sign/{Tos.TosType.IDENTITY_STAKING}/0x1",
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert tos_check_response.status_code == 200
        data = tos_check_response.json()
        assert data["text"].startswith("Hello World !!!")
        assert data["text"].endswith(data["nonce"])

    def test_accept_tos(self, sample_token):
        """Test accepting tos with correct signature."""

        # Create multiple tos, but we only check for the active one in the end
        tos = Tos.objects.create(
            type=Tos.TosType.IDENTITY_STAKING,
            active=True,
            final=True,
            content="Hello World !!!",
        )

        # get a message to sign
        message, nonce = Tos.get_message_with_nonce(Tos.TosType.IDENTITY_STAKING)

        # create an account and sign the messsage
        eth_account = Account.from_mnemonic(settings.TEST_MNEMONIC)

        encoded_message = encode_defunct(text=message)

        signature_obj = eth_account.sign_message(encoded_message)
        signature = signature_obj.signature.hex()

        client = Client()

        tos_check_response = client.post(
            f"/ceramic-cache/tos/signed-message/{Tos.TosType.IDENTITY_STAKING}/0x1",
            json.dumps(
                {
                    "tos_type": Tos.TosType.IDENTITY_STAKING,
                    "nonce": nonce,
                    "signature": signature,
                }
            ),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {sample_token}"},
        )

        assert tos_check_response.status_code == 200
        proof = TosAcceptanceProof.objects.get(
            tos=tos, address=eth_account.address.lower()
        )
        assert proof.nonce == nonce
        assert proof.signature == signature
