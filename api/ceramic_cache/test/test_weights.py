from account.models import Community
from scorer_weighted.models import Scorer, BinaryWeightedScorer
from django.test import Client
from django.conf import settings
import pytest

pytestmark = pytest.mark.django_db  # noqa: F821

client = Client()


class TestGetWeights:
    base_url = "/ceramic-cache"

    def test_get_weights(
        self,
        scorer_account,
    ):
        scorer_weights = {"provider-1": "0.5", "provider-2": "0.5"}
        scorer = BinaryWeightedScorer.objects.create(
            type=Scorer.Type.WEIGHTED_BINARY, weights=scorer_weights
        )

        community = Community.objects.create(
            name="Community 1",
            description="Community 1 - testing",
            account=scorer_account,
            scorer=scorer,
        )

        settings.CERAMIC_CACHE_SCORER_ID = community.pk
        response = client.get(
            f"{self.base_url}/weights",
        )

        returned_weights = response.json()
        assert response.status_code == 200
        assert scorer_weights == returned_weights
