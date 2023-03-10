import re
from decimal import Decimal
from unittest.mock import patch

import pytest
from account.models import Account, Community
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from registry.api import SubmitPassportPayload, get_score, submit_passport
from registry.models import Passport, Score, Stamp
from registry.tasks import score_passport
from web3 import Web3

my_mnemonic = settings.TEST_MNEMONIC
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

mock_passport_data = {
    "stamps": [
        {
            "provider": "Ens",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": "did:pkh:eip155:1:0xa6Cf54ec56BaD8288Ee4559098c48b8D78C05468",
                    "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
                    "provider": "Ens",
                },
                "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
                "issuanceDate": "2023-02-06T23:22:58.848Z",
                "expirationDate": "2099-02-06T23:22:58.848Z",
            },
        },
        {
            "provider": "Gitcoin",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": "did:pkh:eip155:1:0xa6Cf54ec56BaD8288Ee4559098c48b8D78C05468",
                    "hash": "0x45678",
                    "provider": "Gitcoin",
                },
                "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
                "expirationDate": "2099-02-06T23:22:58.848Z",
            },
        },
    ]
}


def mock_validate(*args, **kwargs):
    return []


class TestScorePassportTestCase(TransactionTestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create(username="admin", password="12345")

        account = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        account_2 = web3.eth.account.from_mnemonic(
            my_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        self.account = account
        self.account_2 = account_2

        self.user_account = Account.objects.create(
            user=self.user, address=account.address
        )

        # Mock the default weights for new communities that are created
        with patch(
            "scorer_weighted.models.settings.GITCOIN_PASSPORT_WEIGHTS",
            {
                "Google": 1,
                "Ens": 1,
            },
        ):
            self.community = Community.objects.create(
                name="My Community",
                description="My Community description",
                account=self.user_account,
            )

        self.client = Client()

    def test_no_passport(self):
        with patch("registry.tasks.get_passport", return_value=None):
            score_passport(self.community.pk, self.account.address)

            passport = Passport.objects.get(
                address=self.account.address, community_id=self.community.pk
            )
            self.assertEqual(passport.passport, None)

            score = Score.objects.get(passport=passport)
            self.assertEqual(score.score, None)
            self.assertEqual(score.last_score_timestamp, None)
            self.assertEqual(score.evidence, None)
            self.assertEqual(score.status, Score.Status.ERROR)
            self.assertEqual(score.error, "No Passport found for this address.")

    def test_score_checksummed_address(self):
        address = self.account.address
        assert re.search("[A-Z]", address) is not None

        self._score_address(address)

    def test_score_nonchecksummed_address(self):
        address = self.account.address.lower()
        assert re.search("[A-Z]", address) is None

        self._score_address(address)

    def _score_address(self, address):
        class MockRequest:
            def __init__(self, account):
                self.auth = account

        mock_request = MockRequest(self.user_account)

        with patch("registry.api.score_passport.delay", return_value=None):
            submit_passport(
                mock_request,
                SubmitPassportPayload(
                    address=address,
                    community_id=self.community.pk,
                ),
            )

        with patch("registry.tasks.get_passport", return_value=mock_passport_data):
            with patch("registry.tasks.async_to_sync", return_value=mock_validate):
                score_passport(self.community.pk, address)

        score = get_score(mock_request, address, self.community.pk)
        assert score.score == Decimal("1")
        assert score.status == "DONE"

    def test_cleaning_stale_stamps(self):
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address, community_id=self.community.pk
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            hash="0x1234",
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.tasks.get_passport", return_value=mock_passport_data):
            with patch("registry.tasks.async_to_sync", return_value=mock_validate):
                score_passport(self.community.pk, self.account.address)

                my_stamps = Stamp.objects.filter(passport=passport)
                assert len(my_stamps) == 2

                gitcoin_stamps = my_stamps.filter(provider="Gitcoin")
                assert len(gitcoin_stamps) == 1
                assert gitcoin_stamps[0].hash == "0x45678"
