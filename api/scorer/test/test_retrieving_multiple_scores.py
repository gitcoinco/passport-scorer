"""Retrieve logged Passport scores for Ethereum addresses within a community feature tests."""

import pytest
from django.test import Client
from pytest_bdd import given, scenario, then, when
from registry.models import Passport, Score

pytestmark = pytest.mark.django_db


@scenario(
    "features/retrieve_multiple_scores.feature",
    "Retrieve logged Passport scores for Ethereum addresses within a community",
)
def test_retrieve_logged_passport_scores_for_ethereum_addresses_within_a_community():
    """Retrieve logged Passport scores for Ethereum addresses within a community."""


@given(
    "a list of Ethereum addresses and a community managed by the developer using the API"
)
def _(passport_holder_addresses, scorer_community):
    """a list of Ethereum addresses and a community managed by the developer using the API."""
    for holder in passport_holder_addresses:
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
            passport={"name": "John Doe"},
        )

        stamp = Score.objects.create(
            passport=passport,
            score="1",
        )


@when(
    "the developer makes a request to the API to retrieve the logged Passport scores for the Ethereum addresses within the specified community",
    target_fixture="get_scores_response",
)
def _(passport_holder_addresses, scorer_community, scorer_api_key):
    """the developer makes a request to the API to retrieve the logged Passport scores for the Ethereum addresses within the specified community."""
    client = Client()
    response = client.get(
        f"/registry/scores?community_id={scorer_community.id}&addresses={passport_holder_addresses[0]['address']}&addresses={passport_holder_addresses[1]['address']}",
        HTTP_AUTHORIZATION="Token " + scorer_api_key,
    )
    return response


@then(
    "the API should handle errors and return appropriate messages if any of the Ethereum addresses are invalid or if there are issues with the request."
)
def _(get_scores_response):
    """the API should handle errors and return appropriate messages if any of the Ethereum addresses are invalid or if there are issues with the request.."""
    import pdb

    pdb.set_trace()


@then(
    "the API should return the logged Passport scores for each Ethereum address in the list in a format that is easy to work with (e.g. a JSON object)"
)
def _():
    """the API should return the logged Passport scores for each Ethereum address in the list in a format that is easy to work with (e.g. a JSON object)."""
    # raise NotImplementedError
    pass
