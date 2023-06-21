import re
from decimal import Decimal
from unittest.mock import call, patch

from account.models import Account, AccountAPIKey, Community
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase
from registry.api.v2 import SubmitPassportPayload, get_score, submit_passport
from registry.models import Passport, Score, Stamp
from registry.tasks import score_passport_passport
from web3 import Web3

User = get_user_model()
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
                    "id": settings.TRUSTED_IAM_ISSUER,
                    "hash": "v0.0.0:1Vzw/OyM9CBUkVi/3mb+BiwFnHzsSRZhVH1gaQIyHvM=",
                    "provider": "Ens",
                },
                "issuer": settings.TRUSTED_IAM_ISSUER,
                "issuanceDate": "2023-02-06T23:22:58.848Z",
                "expirationDate": "2099-02-06T23:22:58.848Z",
            },
        },
        {
            "provider": "Gitcoin",
            "credential": {
                "type": ["VerifiableCredential"],
                "credentialSubject": {
                    "id": settings.TRUSTED_IAM_ISSUER,
                    "hash": "0x45678",
                    "provider": "Gitcoin",
                },
                "issuer": settings.TRUSTED_IAM_ISSUER,
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

        AccountAPIKey.objects.create_key(
            account=self.user_account, name="Token for user 1"
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
        with patch("registry.atasks.aget_passport", return_value=None):
            score_passport_passport(self.community.pk, self.account.address)

            passport = Passport.objects.get(
                address=self.account.address, community_id=self.community.pk
            )
            self.assertEqual(passport.stamps.all().count(), 0)

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
                self.api_key = account.api_keys.all()[0]

        mock_request = MockRequest(self.user_account)

        with patch("registry.api.v1.score_passport_passport.delay", return_value=None):
            submit_passport(
                mock_request,
                SubmitPassportPayload(
                    address=address,
                    community=self.community.pk,
                ),
            )

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport_passport(self.community.pk, address)

        Passport.objects.get(address=address, community_id=self.community.pk)

        score = get_score(mock_request, address, self.community.pk)
        assert score.score == Decimal("1")
        assert score.status == "DONE"

    def test_cleaning_stale_stamps(self):
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            hash="0x1234",
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                score_passport_passport(self.community.pk, self.account.address)

                my_stamps = Stamp.objects.filter(passport=passport)
                assert len(my_stamps) == 2

                gitcoin_stamps = my_stamps.filter(provider="Gitcoin")
                assert len(gitcoin_stamps) == 1
                assert gitcoin_stamps[0].hash == "0x45678"

    def test_deduplication_of_scoring_tasks(self):
        """
        Test that when multiple tasks are scheduled for the same Passport, only one of them will execute the scoring calculation, and it will also reset the requires_calculation to False
        """
        passport, _ = Passport.objects.update_or_create(
            address=self.account.address,
            community_id=self.community.pk,
            requires_calculation=True,
        )

        Stamp.objects.filter(passport=passport).delete()

        Stamp.objects.update_or_create(
            hash="0x1234",
            passport=passport,
            defaults={"provider": "Gitcoin", "credential": "{}"},
        )

        assert Stamp.objects.filter(passport=passport).count() == 1

        with patch("registry.atasks.aget_passport", return_value=mock_passport_data):
            with patch(
                "registry.atasks.validate_credential", side_effect=mock_validate
            ):
                with patch("registry.tasks.log.info") as mock_log:
                    # Call score_passport_passport twice, but only one of them should actually execute the scoring calculation
                    score_passport_passport(self.community.pk, self.account.address)
                    score_passport_passport(self.community.pk, self.account.address)

                    expected_call = call(
                        "Passport no passport found for address='%s', community_id='%s' that has requires_calculation=True or None",
                        self.account.address,
                        self.community.pk,
                    )
                    assert mock_log.call_args_list.count(expected_call) == 1
                    assert (
                        Passport.objects.get(pk=passport.pk).requires_calculation
                        is False
                    )
