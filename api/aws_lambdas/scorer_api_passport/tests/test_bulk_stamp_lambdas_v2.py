import json

import pytest
from aws_lambdas.scorer_api_passport.v2.stamps import bulk_DELETE, bulk_PATCH, bulk_POST
from ceramic_cache.models import CeramicCache
from django.conf import settings

from .helpers import MockContext, address, good_stamp, headers

pytestmark = pytest.mark.django_db


def test_patch(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    event = {
        "headers": headers,
        "body": json.dumps(
            [
                good_stamp,
                {"provider": "Facebook"},
            ]
        ),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_PATCH.handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["stamps"][0]["provider"] == "Google"
    assert int(body["score"]["evidence"]["rawScore"]) > 0
    assert body["score"]["status"] == "DONE"
    assert body["success"] == True


def test_delete(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    CeramicCache.objects.create(
        address=address, provider="Google", type=CeramicCache.StampType.V2
    ).save()

    event = {
        "headers": headers,
        "body": json.dumps([{"provider": "Google"}]),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_DELETE.handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert len(body["stamps"]) == 0
    assert int(body["score"]["evidence"]["rawScore"]) == 0
    assert body["score"]["status"] == "DONE"
    assert body["success"] == True


def test_post(
    scorer_community_with_binary_scorer,
    mocker,
    mock_authentication,
):
    settings.CERAMIC_CACHE_SCORER_ID = scorer_community_with_binary_scorer.pk
    event = {
        "headers": headers,
        "body": json.dumps(
            [
                good_stamp,
            ]
        ),
        "isBase64Encoded": False,
    }
    context = MockContext()

    mocker.patch(
        "registry.atasks.avalidate_credentials",
        side_effect=lambda _, passport_data: passport_data,
    )

    response = bulk_POST.handler(event, context)

    body = json.loads(response["body"])

    assert response["statusCode"] == 200
    assert body["stamps"][0]["provider"] == "Google"
    assert int(body["score"]["evidence"]["rawScore"]) > 0
    assert body["score"]["status"] == "DONE"
    assert body["success"] == True
