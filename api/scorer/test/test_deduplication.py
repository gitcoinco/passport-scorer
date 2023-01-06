"""Deduplication rules feature tests."""

import json

import pytest
from account.models import Nonce
from django.test import Client
from eth_account.messages import encode_defunct
from pytest_bdd import given, scenario, then, when
from registry.models import Passport, Stamp
from registry.test.test_passport_submission import (
    ens_credential,
    google_credential,
    mock_passport,
)
from registry.utils import get_signing_message
from web3 import Web3

pytestmark = pytest.mark.django_db

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()


@scenario(
    "features/deduplication.feature",
    "As a developer, I want to rely on LIFO as a default stamp deduplication rule",
)
def test_as_a_developer_i_want_to_rely_on_lifo_as_a_default_stamp_deduplication_rule():
    """As a developer, I want to rely on LIFO as a default stamp deduplication rule."""


@given(
    "that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community",
    target_fixture="submit_passport_response",
)
def _(
    scorer_community_with_gitcoin_default,
    passport_holder_addresses,
    scorer_api_key,
    mocker,
):
    """that a Passport holder submits a stamp with a hash that a different Passport holder previously submitted to the community."""
    # Create the first passport + hashes
    first_passport = Passport.objects.create(
        address=passport_holder_addresses[0]["address"],
        passport=mock_passport,
        community=scorer_community_with_gitcoin_default,
    )

    Stamp.objects.create(
        passport=first_passport,
        hash="hash1",
        provider="Some Provider",
        credential={},
    )

    # Create a stamp, with and ID that will be duplicate
    Stamp.objects.create(
        passport=first_passport,
        hash=ens_credential["credentialSubject"]["hash"],
        provider="Ens",
        credential={},
    )

    # Now submit a second passport with the duplicate hash
    mocker.patch("registry.api.get_passport", return_value=mock_passport)
    mocker.patch("registry.api.validate_credential", side_effect=[[], []])
    client = Client()
    second_account = passport_holder_addresses[1]

    nonce = Nonce.create_nonce().nonce
    signing_message = get_signing_message(nonce)

    signed_message = web3.eth.account.sign_message(
        encode_defunct(text=signing_message),
        private_key=second_account["key"],
    )

    payload = {
        "community": scorer_community_with_gitcoin_default.id,
        "address": second_account["address"],
        "signature": signed_message.signature.hex(),
        "nonce": nonce,
    }

    response = client.post(
        "/registry/submit-passport",
        json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Token {scorer_api_key}",
    )

    return response


@when(
    "we score the associated Passports, i.e., the Passports holding the stamps with identical hashes"
)
def _():
    """we score the associated Passports, i.e., the Passports holding the stamps with identical hashes."""
    pass


@then("score this Passport as if the stamp would be missing")
def _(passport_holder_addresses, submit_passport_response):
    """score this Passport as if the stamp would be missing."""
    # This means ignore the duplicate stamp in the passport that was just submitted
    assert submit_passport_response.status_code == 200
    assert submit_passport_response.json() == [
        {
            "address": passport_holder_addresses[1]["address"].lower(),
            "score": "1234.000000000",  # we expect a score only for the ENS stamp
            "error": None,
        }
    ]


@then(
    "we don't recognize the version of the stamp that has been more recently submitted"
)
def _():
    """we don't recognize the version of the stamp that has been more recently submitted."""
    # Covered in the previews step
    pass
