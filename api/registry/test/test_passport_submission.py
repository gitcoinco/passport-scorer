import binascii
import copy
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from account.models import Account, AccountAPIKey, Community, Nonce
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TransactionTestCase
from eth_account.messages import encode_defunct
from registry.models import Passport, Stamp
from registry.tasks import score_passport
from registry.utils import get_signer, get_signing_message, verify_issuer
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

my_mnemonic = settings.TEST_MNEMONIC

ens_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}

ens_credential_corrupted = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..b_ek317zi0Gq3SylrtJeODlbZuRrzfv-1TTBBNcBrDTMDBTikzPJMR2A1SuVcrfUl3MpNZ-zymaLGB5qz9xdDg",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:22.279Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC"
        + "CORRUPTING THE FIELD",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:xG1Todke+0P1jphcnZhP/3UA5XUBMaEux4fHG86I20U=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Ens",
    },
}


google_credential = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxtHSqdiPpEXR06Ejw+YLO9K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}


google_credential_2 = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() + timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxthSqdilpEXR06Ojw+YLO8K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}


google_credential_expired = {
    "type": ["VerifiableCredential"],
    "proof": {
        "jws": "eyJhbGciOiJFZERTQSIsImNyaXQiOlsiYjY0Il0sImI2NCI6ZmFsc2V9..UvANt5nz16WNjkGTyUFIxbMBmYdEFZcVrD97L3EzOkvxz8eN-6UKeFZul_uPBfa88h50jKQgVgJlJqxR8kpSAQ",
        "type": "Ed25519Signature2018",
        "created": "2022-06-03T15:33:04.698Z",
        "proofPurpose": "assertionMethod",
        "verificationMethod": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC#z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    },
    "issuer": "did:key:z6MkghvGHLobLEdj1bgRLhS4LPGJAvbMA1tn2zcRyqmYU5LC",
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "issuanceDate": (datetime.utcnow() - timedelta(days=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "expirationDate": (datetime.utcnow() - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    ),
    "credentialSubject": {
        "id": "did:pkh:eip155:1:0x0636F974D29d947d4946b2091d769ec6D2d415DE",
        "hash": "v0.0.0:edgFWHsCSaqGxtHSqdiPpEXR06Ejw+YLO9K0BSjz0d8=",
        "@context": [
            {
                "hash": "https://schema.org/Text",
                "provider": "https://schema.org/Text",
            }
        ],
        "provider": "Google",
    },
}

mock_utc_timestamp = datetime(2015, 2, 1, 15, 16, 17, 345, tzinfo=timezone.utc)

mock_passport = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Google", "credential": google_credential},
    ],
}

mock_passport_2 = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Google", "credential": google_credential_2},
    ],
}

mock_passport_google = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential_2},
    ],
}

mock_passport_with_corrupted_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": ens_credential_corrupted},
    ],
}


mock_passport_with_expired_stamp = {
    "issuanceDate": "2022-06-03T15:31:56.944Z",
    "expirationDate": "2022-06-03T15:31:56.944Z",
    "stamps": [
        {"provider": "Google", "credential": google_credential},
        {"provider": "Ens", "credential": ens_credential},
        {"provider": "Ens", "credential": google_credential_expired},
    ],
}


class ValidatePassportTestCase(TransactionTestCase):
    def setUp(self):
        # Just create 1 user, to make sure the user id is different than account id
        # This is to catch errors like the one where the user id is the same as the account id, and
        # we query the account id by the user id
        self.user = User.objects.create_user(username="admin", password="12345")

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

        self.nonce = Nonce.create_nonce().nonce
        self.nonce_2 = Nonce.create_nonce().nonce

        self.signing_message = get_signing_message(self.nonce)
        self.signing_message_2 = get_signing_message(self.nonce_2)

        self.signed_message = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.account.key,
        )
        self.signed_message_2 = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.account_2.key,
        )

        self.user2 = User.objects.create_user(username="admin2", password="12345")
        self.user_account2 = Account.objects.create(user=self.user2, address="0x02")
        self.community2 = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=self.user_account2,
        )

        (account_api_key, secret) = AccountAPIKey.objects.create_key(
            account=self.user_account, name="Token for user 1"
        )
        self.account_api_key = account_api_key
        self.secret = secret

        mock_mnemonic = "tourist search plug company mail blind arch rather angry captain spin reform"
        mock_account = web3.eth.account.from_mnemonic(
            mock_mnemonic, account_path="m/44'/60'/0'/0/0"
        )
        self.mock_account = mock_account
        self.mock_signed_message = web3.eth.account.sign_message(
            encode_defunct(text=self.signing_message),
            private_key=self.mock_account.key,
        )

        self.client = Client()

    def test_invalid_api_key(self):
        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "community_id": self.community.id,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Token 1234",
        )

        self.assertEqual(response.status_code, 401)

    def test_verify_signature(self):
        signer = get_signer(self.nonce, self.signed_message.signature.hex())
        self.assertEqual(signer, self.account.address)

    def test_verify_signature_wrong_signature(self):
        """Compare signature of account_2 against account"""
        # Change the signature
        signature = bytearray(self.signed_message_2.signature)
        signature[0] = signature[0]
        signature = bytes(signature)

        signer = get_signer(self.nonce_2, signature)
        self.assertNotEqual(signer, self.account.address)

    @patch("registry.tasks.validate_credential", side_effect=[[], []])
    @patch("registry.tasks.get_passport", return_value=mock_passport)
    def test_signature_not_needed_by_default(self, get_passport, validate_credential):
        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_valid_issuer(self):
        valid = verify_issuer(mock_passport["stamps"][1])
        self.assertEqual(valid, True)

    @patch("registry.tasks.validate_credential", side_effect=[[], []])
    @patch("registry.tasks.get_passport", return_value=mock_passport)
    def test_submit_passport(self, get_passport, validate_credential):
        # get_passport.return_value = mock_passport

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

        score_passport(self.community.id, self.account.address)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.tasks.validate_credential", side_effect=[[], []])
    @patch("registry.tasks.get_passport", return_value=mock_passport)
    def test_submit_passport_reused_nonce(self, get_passport, validate_credential):
        """Test that submitting a reused nonce results in rejection"""

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        for _ in [1, 2]:
            response = self.client.post(
                "/registry/submit-passport",
                json.dumps(payload),
                **{
                    "content_type": "application/json",
                    "HTTP_AUTHORIZATION": f"Token {self.secret}",
                },
            )

        self.assertEqual(response.json(), {"detail": "Invalid nonce."})
        self.assertEqual(response.status_code, 400)

    @patch("registry.tasks.validate_credential", side_effect=[[], []])
    @patch("registry.tasks.get_passport", return_value={})
    def test_submitting_without_passport(self, get_passport, validate_credential):
        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/json",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)

        score_passport(self.community.id, self.account.address)

        # Check if the passport data was saved to the database (data that we mock)
        # We do expect an empty passport to have been stored
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, None)

        response = self.client.get(
            f"/registry/score/{self.community.id}/{self.account.address}",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        assert response.status_code == 200
        assert response.json() == {
            "address": self.account.address.lower(),
            "score": None,
            "evidence": None,
            "last_score_timestamp": None,
            "status": "ERROR",
            "error": "No Passport found for this address.",
        }

    @patch("registry.tasks.validate_credential", side_effect=[[], [], [], []])
    @patch(
        "registry.tasks.get_passport",
        side_effect=[copy.deepcopy(mock_passport), copy.deepcopy(mock_passport)],
    )
    @patch(
        "registry.tasks.get_utc_time",
        return_value=datetime.fromisoformat("2023-01-11T16:35:23.938006+00:00"),
    )
    def test_submit_passport_multiple_times(self, _, get_passport, validate_credential):
        """Verify that submitting the same address multiple times only registers each stamp once, and gives back the same score"""
        # get_passport.return_value = mock_passport

        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        expectedResponse = {
            "score": None,
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "evidence": None,
            "last_score_timestamp": None,
            "score": None,
            "status": "PROCESSING",
            "error": None,
        }

        expected2ndResponse = {
            "score": None,
            "address": "0xb81c935d01e734b3d8bb233f5c4e1d72dbc30f6c",
            "evidence": None,
            "last_score_timestamp": "2023-01-11T16:35:23.938006+00:00",
            "score": None,
            "status": "PROCESSING",
            "error": None,
        }

        # First submission
        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/tson",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            expectedResponse,
        )

        score_passport(self.community.id, self.account.address)

        # 2nd submission
        # Get another nonce (nonces can only be used once)
        nonce = Nonce.create_nonce().nonce
        signing_message = get_signing_message(nonce)
        signed_message = web3.eth.account.sign_message(
            encode_defunct(text=signing_message),
            private_key=self.account_2.key,
        )

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": signed_message.signature.hex(),
            "nonce": nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            **{
                "content_type": "application/tson",
                "HTTP_AUTHORIZATION": f"Token {self.secret}",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            expected2ndResponse,
        )

        score_passport(self.community.id, self.account.address)

        # Check that the stamps have only been recorded once
        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)

        self.assertEqual(all_passports[0].passport, mock_passport)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.tasks.get_passport", return_value=mock_passport)
    def test_submit_passport_missing_community(self, get_passport):
        """
        Make sure that the community is required when submitting eth address
        """
        did = f"did:pkh:eip155:1:{self.account.address.lower()}"

        payload = {
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 422)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 0)

    @patch(
        "registry.tasks.validate_credential",
        side_effect=[[], [], ["Stamp validation failed: invalid date"]],
    )
    @patch(
        "registry.tasks.get_passport",
        return_value=mock_passport_with_corrupted_stamp,
    )
    def test_submit_passport_with_invalid_stamp(
        self, get_passport, validate_credential
    ):
        """
        Verify that stamps which do not pass the didkit validation are ignored and not stored in the DB
        """

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        score_passport(self.community.id, self.account.address)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport_with_corrupted_stamp)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.tasks.validate_credential", side_effect=[[], [], []])
    @patch(
        "registry.tasks.get_passport",
        return_value=mock_passport_with_expired_stamp,
    )
    def test_submit_passport_with_expired_stamps(
        self, get_passport, validate_credential
    ):
        """
        Verify that stamps that are expired are ignored
        """

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        score_passport(self.community.id, self.account.address)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport_with_expired_stamp)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(len(all_passports[0].stamps.all()), 2)
        stamp_ens = Stamp.objects.get(provider="Ens")
        stamp_google = Stamp.objects.get(provider="Google")

        self.assertEqual(stamp_ens.credential, ens_credential)
        self.assertEqual(stamp_google.credential, google_credential)
        self.assertEqual(stamp_ens.hash, ens_credential["credentialSubject"]["hash"])
        self.assertEqual(
            stamp_google.hash, google_credential["credentialSubject"]["hash"]
        )

    @patch("registry.tasks.validate_credential", side_effect=[[], [], []])
    @patch(
        "registry.tasks.get_passport",
        return_value=mock_passport,
    )
    def test_that_community_is_associated_with_passport(
        self, get_passport, validate_credential
    ):
        """
        Verify that the community is associated with the passport
        """

        payload = {
            "community_id": self.community.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 200)

        score_passport(self.community.id, self.account.address)

        # Check if the passport data was saved to the database (data that we mock)
        all_passports = list(Passport.objects.all())
        self.assertEqual(len(all_passports), 1)
        self.assertEqual(all_passports[0].passport, mock_passport)
        self.assertEqual(all_passports[0].address, self.account.address.lower())
        self.assertEqual(all_passports[0].community, self.community)

    @patch(
        "registry.tasks.get_passport",
        return_value=mock_passport,
    )
    def test_that_only_owned_communities_can_submit_passport(self, get_passport):
        """
        Verify that only communities owned by the user of the API key can create passports
        """

        payload = {
            "community_id": self.community2.id,
            "address": self.account.address,
            "signature": self.signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        response = self.client.post(
            "/registry/submit-passport",
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )
        self.assertEqual(response.status_code, 404)

    @patch("registry.tasks.validate_credential", side_effect=[[], []])
    @patch(
        "registry.tasks.get_passport",
        return_value=mock_passport_google,
    )
    def test_lifo_deduplication_duplicate_stamps(
        self, get_passport, validate_credential
    ):
        """
        Test the successful deduplication of stamps by last in first out (LIFO)
        """

        address_1 = self.account.address.lower()
        submission_address = self.mock_account.address.lower()

        # Create first passport
        first_passport = Passport.objects.create(
            address=address_1,
            passport=mock_passport,
            community=self.community,
        )

        Stamp.objects.create(
            passport=first_passport,
            hash=ens_credential["credentialSubject"]["hash"],
            provider="Ens",
            credential=ens_credential,
        )

        Stamp.objects.create(
            passport=first_passport,
            hash=google_credential["credentialSubject"]["hash"],
            provider="Google",
            credential=google_credential,
        )

        # Now we submit a duplicate hash, and expect deduplication to happen
        submission_test_payload = {
            "community_id": self.community.id,
            "address": self.mock_account.address,
            "signature": self.mock_signed_message.signature.hex(),
            "nonce": self.nonce,
        }

        submission_response = self.client.post(
            "/registry/submit-passport",
            json.dumps(submission_test_payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {self.secret}",
        )

        score_passport(self.community.pk, self.mock_account.address)

        self.assertEqual(submission_response.status_code, 200)

        updated_passport = Passport.objects.get(address=submission_address)

        self.assertEqual(len(updated_passport.passport["stamps"]), 1)
        self.assertEqual(updated_passport.address, submission_address)
        self.assertEqual(updated_passport.passport, mock_passport_google)
        self.assertEqual(updated_passport.passport["stamps"][0]["provider"], "Google")
