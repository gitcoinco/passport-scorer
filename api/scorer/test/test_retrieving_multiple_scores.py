"""Retrieve logged Passport scores for Ethereum addresses within a community feature tests."""

import pytest
from django.test import Client
from pytest_bdd import given, scenario, then, when
from registry.models import Passport, Score

pytestmark = pytest.mark.django_db

client = Client()


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

    response = client.get(
        f"/registry/scores?community_id={scorer_community.id}&addresses={passport_holder_addresses[0]['address']}&addresses={passport_holder_addresses[1]['address']}&addresses='bad_address",
        HTTP_AUTHORIZATION="Token " + scorer_api_key,
    )
    return response


@then(
    "the API should handle errors and return appropriate messages if any of the Ethereum addresses are invalid or if there are issues with the request."
)
def _(get_scores_response, passport_holder_addresses, scorer_api_key):
    """the API should handle errors and return appropriate messages if any of the Ethereum addresses are invalid or if there are issues with the request.."""
    results = get_scores_response.json()
    assert get_scores_response.status_code == 200
    assert results[2]["error"] == "Unable to find score for given address"

    response = client.get(
        f"/registry/scores?community_id=bad_community&addresses={passport_holder_addresses[0]['address']}&addresses={passport_holder_addresses[1]['address']}&addresses='bad_address",
        HTTP_AUTHORIZATION="Token " + scorer_api_key,
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "value is not a valid integer"


@then(
    "the API should return the logged Passport scores for each Ethereum address in the list in a format that is easy to work with (e.g. a JSON object)"
)
def _(get_scores_response):
    """the API should return the logged Passport scores for each Ethereum address in the list in a format that is easy to work with (e.g. a JSON object)."""
    results = get_scores_response.json()
    assert results[0]["score"] == "1.000000000"
    assert results[1]["score"] == "1.000000000"
    assert results[2]["score"] == ""
