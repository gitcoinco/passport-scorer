import pytest
from account.models import Account, AccountAPIKey, Community
from django.contrib.auth.models import User
from django.test import Client
from registry.models import Passport, Score, Stamp
from web3 import Web3

web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()

# TODO: Load from fixture file
pytestmark = pytest.mark.django_db


@pytest.fixture
def scorer_user():
    user = User.objects.create_user(username="testuser-1", password="12345")
    print("scorer_user user", user)
    return user


@pytest.fixture
def scorer_account(scorer_user):
    # TODO: load mnemonic from env
    my_mnemonic = (
        "chief loud snack trend chief net field husband vote message decide replace"
    )
    web3_account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )

    print("scorer_user", scorer_user)
    print("web3_account.address", web3_account.address)
    account = Account.objects.create(user=scorer_user, address=web3_account.address)
    return account


@pytest.fixture
def scorer_api_key(scorer_account):
    (account_api_key, secret) = AccountAPIKey.objects.create_key(
        account=scorer_account, name="Token for user 1"
    )
    return secret


@pytest.fixture
def scorer_community(scorer_account):
    community = Community.objects.create(
        name="My Community",
        description="My Community description",
        account=scorer_account,
    )
    return community


@pytest.fixture
def scorer_passport(scorer_account, scorer_community):
    passport = Passport.objects.create(
        address=scorer_account.address,
        passport={"name": "John Doe"},
        community=scorer_community,
    )
    return passport


@pytest.fixture
def scorer_score(scorer_passport):
    stamp = Score.objects.create(
        passport=scorer_passport,
        score="0.650000000",
    )
    return stamp


class TestPassportGetScore:
    def test_passport_get_scores(
        self, scorer_api_key, scorer_community, scorer_account, scorer_score
    ):
        address = scorer_account.address
        community_id = scorer_community.id
        client = Client()
        response = client.get(
            f"/registry/score/{community_id}/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200
        assert response.json() == {
            "address": address.lower(),
            "score": scorer_score.score,
            "error": None,
        }

    # TODO: Create test authorization separately
    def test_passport_get_scores_no_auth(self, scorer_community, scorer_account):
        address = scorer_account.address
        community_id = scorer_community.id
        client = Client()
        response = client.get(
            f"/registry/score/{community_id}/{address}",
        )
        assert response.status_code == 401

    def test_passport_get_scores_bad_community(self, scorer_api_key, scorer_account):
        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/score/3/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 400

    def test_get_score_with_valid_community_with_no_scores(
        self, scorer_api_key, scorer_account
    ):
        additional_community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=scorer_account,
        )

        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/score/{additional_community.id}/{address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400

    def test_get_scores_with_valid_community_with_no_scores(
        self, scorer_api_key, scorer_account
    ):
        additional_community = Community.objects.create(
            name="My Community",
            description="My Community description",
            account=scorer_account,
        )

        address = scorer_account.address
        client = Client()
        response = client.get(
            f"/registry/scores?community_id={additional_community.id}&addresses={address}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 400
