"""
This module contains tests for the data science bulk score functionality.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from registry.models import BatchModelScoringRequest, BatchRequestStatus

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def batch_requests():
    now = timezone.now()
    requests = []
    for i in range(15):
        status = BatchRequestStatus.DONE if i % 3 == 0 else BatchRequestStatus.PENDING
        requests.append(
            BatchModelScoringRequest.objects.create(
                created_at=now - timedelta(hours=i),
                s3_filename=f"test_file_{i}.csv",
                status=status,
                progress=100 if status == BatchRequestStatus.DONE else i * 10,
            )
        )
    return requests


api_url = "/internal/analysis/internal"


def test_get_batch_analysis_stats_success(client, batch_requests, mocker):
    mock_s3_client = mocker.Mock()
    mock_s3_client.generate_presigned_url.return_value = (
        "https://example.com/presigned-url"
    )
    with mocker.patch("registry.api.v2.get_s3_client", return_value=mock_s3_client):
        response = client.get(api_url, HTTP_AUTHORIZATION=settings.DATA_SCIENCE_API_KEY)

        assert response.status_code == 200
        data = response.json()

        assert len(data) == 10  # Default limit
        assert all(isinstance(item, dict) for item in data)

        for item in data:
            assert "created_at" in item
            assert "s3_url" in item
            assert "status" in item
            assert "percentage_complete" in item

        # Check if the items are ordered by created_at in descending order
        assert all(
            data[i]["created_at"] >= data[i + 1]["created_at"]
            for i in range(len(data) - 1)
        )

        # Check if DONE requests have s3_url and others don't
        for item in data:
            if item["status"] == BatchRequestStatus.DONE.value:
                assert item["s3_url"] == "https://example.com/presigned-url"
            else:
                assert item["s3_url"] is None


def test_get_batch_analysis_stats_with_limit(client, batch_requests, mocker):
    mock_s3_client = mocker.Mock()
    mock_s3_client.generate_presigned_url.return_value = (
        "https://example.com/presigned-url"
    )
    with mocker.patch("registry.api.v2.get_s3_client", return_value=mock_s3_client):
        response = client.get(
            f"{api_url}?limit=5", HTTP_AUTHORIZATION=settings.DATA_SCIENCE_API_KEY
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5


def test_get_batch_analysis_stats_unauthorized(client):
    response = client.get(api_url)
    assert response.status_code == 401


def test_get_batch_analysis_stats_wrong_key(client):
    response = client.get(api_url, HTTP_AUTHORIZATION="wrong_key")
    assert response.status_code == 401


def test_get_batch_analysis_stats_empty_result(client):
    response = client.get(api_url, HTTP_AUTHORIZATION=settings.DATA_SCIENCE_API_KEY)

    assert response.status_code == 200
    assert response.json() == []
