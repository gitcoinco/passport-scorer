from datetime import datetime

import pytest
from account.models import Nonce
from django.conf import settings

# pylint: disable=unused-import
from scorer.test.conftest import (
    access_token,
    scorer_account,
    scorer_community,
    scorer_user,
)
from web3 import Web3

my_mnemonic = settings.TEST_MNEMONIC


@pytest.fixture
def nonce():
    Nonce.create_nonce().nonce


@pytest.fixture
def web3_account():
    web3 = Web3()
    web3.eth.account.enable_unaudited_hdwallet_features()
    account = web3.eth.account.from_mnemonic(
        my_mnemonic, account_path="m/44'/60'/0'/0/0"
    )
    return account


@pytest.fixture
def siwe_data(nonce):
    return {
        "domain": "localhost:3000",
        "address": web3_account.address,
        "statement": f"Welcome to Gitcoin Passport Scorer! This request will not trigger a blockchain transaction or cost any gas fees. Your authentication status will reset in 24 hours. Wallet Address: ${account.address}. Nonce: ${nonce}",
        "uri": "http://localhost/",
        "version": "1",
        "chainId": "1",
        "nonce": nonce.nonce,
        "issuedAt": datetime.utcnow().isoformat(),
    }
