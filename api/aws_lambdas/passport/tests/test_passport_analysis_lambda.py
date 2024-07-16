# pylint: disable=no-value-for-parameter
# pyright: reportGeneralTypeIssues=false
import json

import pytest
from django.conf import settings

from aws_lambdas.scorer_api_passport.tests.helpers import MockContext

from ..analysis_GET import _handler

pytestmark = pytest.mark.django_db

address = "0x06e3c221011767FE816D0B8f5B16253E43e4Af7D"


def mock_post_response(session, url, data):
    # Create a mock response object
    # mock_response = Mock()
    # mock_response.status_code = 200

    # Define different responses based on the model (which we can infer from the URL)
    responses = {
        "ethereum_activity": {
            "data": {"human_probability": 75},
            "metadata": {"model_name": "ethereum_activity", "version": "1.0"},
        },
        "nft": {
            "data": {"human_probability": 85},
            "metadata": {"model_name": "social_media", "version": "2.0"},
        },
        "zksync": {
            "data": {"human_probability": 95},
            "metadata": {"model_name": "transaction_history", "version": "1.5"},
        },
    }

    # Determine which model is being requested
    for model, endpoint in settings.MODEL_ENDPOINTS.items():
        if endpoint in url:
            response_data = responses.get(model, {"data": {"human_probability": 0}})
            break
    else:
        response_data = {"error": "Unknown model"}

    # Set the json method of the mock response
    # mock_response.json = lambda: response_data

    # print("*" * 40)
    # print("mock_response: ", mock_response)
    # print("*" * 40)
    # return mock_response
    return response_data


def test_successful_analysis_eth(
    scorer_api_key,
    mocker,
):
    """
    Tests that analysis can be requested successfully.
    """

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {"model_list": "ethereum_activity"},
        "isBase64Encoded": False,
    }
    with mocker.patch("passport.api.fetch", side_effect=mock_post_response):
        response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert body["address"] == address
    assert body["details"]["models"]["ethereum_activity"]["score"] == 75


def test_bad_auth(
    mocker,
):
    """
    Tests that error is thrown if auth is bad
    """

    event = {
        "headers": {"x-api-key": "bad_auth"},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 401
    assert json.loads(response["body"])["error"] == "Invalid API Key."


def test_bad_address(
    scorer_api_key,
    mocker,
):
    """
    Tests that error is thrown is addrss is bad
    """

    bad_address = address[:-1] + "d"

    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{bad_address}",
        "queryStringParameters": {},
        "isBase64Encoded": False,
    }
    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "Invalid address."


def test_bad_model(
    scorer_api_key,
    mocker,
):
    """
    Tests that error is thrown if unsupported model is requested
    """

    model = "bad_model"
    event = {
        "headers": {"x-api-key": scorer_api_key},
        "path": f"/passport/analysis/{address}",
        "queryStringParameters": {"model_list": model},
        "isBase64Encoded": False,
    }

    response = _handler(event, MockContext())

    assert response is not None
    assert response["statusCode"] == 400
    assert (
        json.loads(response["body"])["error"]
        == f"Invalid model name(s): {', '.join([model])}. Must be one of {', '.join(settings.MODEL_ENDPOINTS.keys())}"
    )
