import datetime
from datetime import datetime as dt
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from registry.models import Event, Passport, Score
from registry.test.test_passport_get_score import TestPassportGetScore
from web3 import Web3

User = get_user_model()
web3 = Web3()
web3.eth.account.enable_unaudited_hdwallet_features()
my_mnemonic = settings.TEST_MNEMONIC

pytestmark = pytest.mark.django_db


@pytest.fixture
def paginated_scores(scorer_passport, passport_holder_addresses, scorer_community):
    """
    Return an ordered list of scores (that is also saved in the DB).
    last_score_timestamp - will be incresaing from first to last, with a time delta of 1 day
    """
    scores = []
    events = []
    i = 0
    for holder in passport_holder_addresses:
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
        )

        score = Score.objects.create(
            status="DONE",
            passport=passport,
            score="1",
            last_score_timestamp=timezone.now() + datetime.timedelta(days=i + 1),
        )

        scores.append(score)
        i += 1
    return scores


@pytest.fixture
def shuffled_paginated_scores(
    scorer_passport, passport_holder_addresses, scorer_community
):
    scores = []

    timestamps = [
        "2023-08-15 12:22:23.090489+00:00",
        "2023-08-01 15:11:45.091219+00:00",
        "2023-08-03 15:11:45.089987+00:00",
        "2023-08-06 15:11:45.088379+00:00",
        "2023-08-06 15:11:45.088379+00:00",
        "2023-08-21 15:11:45.090981+00:00",
        "2023-08-04 15:11:45.089262+00:00",
        "2023-08-06 15:11:45.088379+00:00",
        "2023-08-26 15:11:45.088988+00:00",
        "2023-08-07 15:11:45.090489+00:00",
    ]

    for i, holder in enumerate(passport_holder_addresses):
        passport = Passport.objects.create(
            address=holder["address"],
            community=scorer_community,
        )

        score = Score.objects.create(
            passport=passport, score="1", last_score_timestamp=timestamps[i]
        )
        scores.append(score)

    return scores


class TestPassportGetScoreV2(TestPassportGetScore):
    base_url = "/registry/v2"

    def test_get_scores_returns_first_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 2

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        assert response.status_code == 200
        assert response_data["prev"] == None

        next_page = client.get(
            response_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert next_page.status_code == 200

        for i in range(limit):
            assert (
                response_data["items"][i]["address"]
                == passport_holder_addresses[i]["address"].lower()
            )

    def test_get_scores_returns_second_page_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 2

        client = Client()
        page_one_response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_one_data = page_one_response.json()

        assert page_one_response.status_code == 200

        page_two_response = client.get(
            page_one_data["next"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        page_two_data = page_two_response.json()

        assert page_two_response.status_code == 200

        page_two_prev = client.get(
            page_two_data["prev"],
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert page_two_prev.status_code == 200
        assert page_two_prev.json() == page_one_data

        for i in range(limit):
            assert (
                page_two_data["items"][i]["address"]
                == passport_holder_addresses[i + limit]["address"].lower()
            )

    def test_get_scores_filter_by_last_score_timestamp__gte(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        now = datetime.datetime.utcnow()
        past_time_stamp = now - datetime.timedelta(days=1)
        future_time_stamp = now + datetime.timedelta(days=1)

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        for score in older_scores:
            score.last_score_timestamp = past_time_stamp
            score.save()

        # The first score will have a last_score_timestamp equal to the value we filter by
        for idx, score in enumerate(newer_scores):
            if idx == 0:
                score.last_score_timestamp = now
            else:
                score.last_score_timestamp = future_time_stamp
            score.save()

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gte={now.isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gte={(now - datetime.timedelta(milliseconds=1)).isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

    def test_get_scores_filter_by_last_score_timestamp__gt(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        now = datetime.datetime.utcnow()
        past_time_stamp = now - datetime.timedelta(days=1)
        future_time_stamp = now + datetime.timedelta(days=1)

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        for score in older_scores:
            score.last_score_timestamp = past_time_stamp
            score.save()

        # The first score will have a last_score_timestamp equal to the value we filter by
        for idx, score in enumerate(newer_scores):
            if idx == 0:
                score.last_score_timestamp = now
            else:
                score.last_score_timestamp = future_time_stamp
            score.save()

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gt={now.isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores) - 1

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"/registry/score/{scorer_community.id}?last_score_timestamp__gt={(now - datetime.timedelta(milliseconds=1)).isoformat()}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == len(newer_scores)

    def test_v2_get_scores_filter_by_last_score_timestamp__gte(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        timestamp_to_filter_by = newer_scores[0].last_score_timestamp

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"last_score_timestamp__gte": timestamp_to_filter_by.isoformat()},
        )

        assert response.status_code == 200
        response_data = response.json()["items"]
        assert len(response_data) == len(newer_scores)
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores
        ]

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={
                "last_score_timestamp__gte": (
                    timestamp_to_filter_by - datetime.timedelta(milliseconds=1)
                ).isoformat()
            },
        )
        assert response.status_code == 200
        response_data = response.json()["items"]
        assert len(response_data) == len(newer_scores)
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores
        ]

    def test_v2_get_scores_pagination_when_having_multiple_identical_timestamps(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        shuffled_paginated_scores,
    ):
        """
        Thi tests wants to ensure that when having multiple identical timestamps, the order of the scores
        is properly handled when paginating with prev and next.
        We split the set of scores into 2, such that the timestamps in the last one of rthe first set and
        first one in the 2nd set are identical, and paginate around that split.
        """
        timestamps = [s.last_score_timestamp for s in shuffled_paginated_scores]

        # We pick a duplicate timestamp, and we'll paginate around that
        timestamp_idx = timestamps.index("2023-08-06 15:11:45.088379+00:00")

        scores = list(Score.objects.order_by("last_score_timestamp", "id"))
        newer_scores = scores[: timestamp_idx + 1]
        older_scores = scores[timestamp_idx + 1 :]

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2
        assert (
            newer_scores[-1].last_score_timestamp
            == older_scores[0].last_score_timestamp
        )

        ##########################################
        # Read first page
        ##########################################
        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={
                "limit": timestamp_idx + 1,
            },
        )

        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        next_page = response_json["next"]
        assert len(response_data) == len(newer_scores)
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores
        ]

        ##########################################
        # Read 2nd page with next
        ##########################################
        response = client.get(
            next_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        prev_page = response_json["prev"]
        expected_length = min(len(older_scores), timestamp_idx + 1)
        assert len(response_data) == expected_length
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in older_scores[:expected_length]
        ]

        ##########################################
        # Read 1st page with prev
        ##########################################
        response = client.get(
            prev_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        assert len(response_data) == len(newer_scores)
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores
        ]

    def test_v2_get_scores_pagination_when_identical_timestamps(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]
        timestamp_to_filter_by = newer_scores[0].last_score_timestamp

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        ##########################################
        # Read first page
        ##########################################
        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={
                "last_score_timestamp__gte": timestamp_to_filter_by.isoformat(),
                "limit": 2,
            },
        )

        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        next_page = response_json["next"]
        assert len(response_data) == 2
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[:2]
        ]

        ##########################################
        # Read 2nd page with next
        ##########################################
        response = client.get(
            next_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        next_page = response_json["next"]
        assert len(response_data) == 2
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[2:4]
        ]

        ##########################################
        # Read 3rd and last page with next
        ##########################################
        response = client.get(
            next_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        prev_page = response_json["prev"]
        assert response_json["next"] == None
        assert len(response_data) == 1
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[4:5]
        ]

        ##########################################
        # Read 2nd page with prev
        ##########################################
        response = client.get(
            prev_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        prev_page = response_json["prev"]
        assert len(response_data) == 2
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[2:4]
        ]

        ##########################################
        # Read first page with prev
        ##########################################
        response = client.get(
            prev_page,
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        assert response.status_code == 200
        response_json = response.json()
        response_data = response_json["items"]
        # assert response_json["prev"] == None
        assert len(response_data) == 2
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[:2]
        ]

    def test_v2_get_scores_filter_by_last_score_timestamp__gt(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        older_scores = scores[:middle]
        newer_scores = scores[middle:]

        # Make sure we have sufficient data in both queries
        assert len(newer_scores) >= 2
        assert len(older_scores) >= 2

        timestamp_to_filter_by = newer_scores[0].last_score_timestamp

        # Check the query when the filtered timestamp equals a score last_score_timestamp
        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"last_score_timestamp__gt": timestamp_to_filter_by.isoformat()},
        )

        assert response.status_code == 200
        response_data = response.json()["items"]
        assert (
            len(response_data) == len(newer_scores) - 1
        )  # -1 is there because we used the `_gt` filter and not the `_gte`
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores[1:]
        ]

        # Check the query when the filtered timestamp does not equal a score last_score_timestamp
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={
                "last_score_timestamp__gt": (
                    timestamp_to_filter_by - datetime.timedelta(milliseconds=1)
                ).isoformat()
            },
        )
        assert response.status_code == 200
        response_data = response.json()["items"]
        assert len(response_data) == len(newer_scores)
        assert response_data == [
            {
                "address": s.passport.address,
                "score": str(s.score),
                "status": s.status,
                "last_score_timestamp": s.last_score_timestamp.isoformat(),
                "evidence": s.evidence,
                "error": s.error,
                "stamp_scores": {},
            }
            for s in newer_scores
        ]

    def test_get_scores_with_shuffled_ids(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        shuffled_paginated_scores,
    ):
        limit = 5
        scores = list(Score.objects.all())
        middle = len(scores) // 2
        top_half_scores = scores[:middle]
        bottom_half_scores = scores[middle:]

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        first_response_data = response.json()

        assert response.status_code == 200
        assert len(first_response_data["items"]) == len(top_half_scores)

        first_five_scores = Score.objects.order_by("last_score_timestamp")[:5]

        for score, item in zip(first_five_scores, first_response_data["items"]):
            dt_res_score = item["last_score_timestamp"]
            dt_res_score_object = dt.fromisoformat(dt_res_score)
            dt_res_score_object_str_space = dt_res_score_object.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            dt_last_score_string = score.last_score_timestamp.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            assert dt_last_score_string == dt_res_score_object_str_space

        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        last_response_data = response.json()
        assert response.status_code == 200
        assert len(last_response_data["items"]) == len(bottom_half_scores)

        last_five_scores = Score.objects.order_by("last_score_timestamp")[:5]

        for score, item in zip(last_five_scores, last_response_data["items"]):
            dt_res_score = item["last_score_timestamp"]
            dt_res_score_object = dt.fromisoformat(dt_res_score)
            dt_res_score_object_str_space = dt_res_score_object.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            dt_last_score_string = score.last_score_timestamp.strftime(
                "%Y-%m-%d %H:%M:%S.%f%z"
            )
            assert dt_last_score_string == dt_res_score_object_str_space

    def test_last_score_timestamp(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 10
        scores = list(Score.objects.all())

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )
        response_data = response.json()

        last_score = scores[len(scores) - 1]
        last_response_score = response_data["items"][len(response_data["items"]) - 1]

        dt_res_score = last_response_score["last_score_timestamp"]
        dt_res_score_object = dt.fromisoformat(dt_res_score)
        dt_res_score_object_str_space = dt_res_score_object.strftime(
            "%Y-%m-%d %H:%M:%S.%f%z"
        )
        dt_last_score_string = last_score.last_score_timestamp.strftime(
            "%Y-%m-%d %H:%M:%S.%f%z"
        )

        assert response.status_code == 200
        assert dt_last_score_string == dt_res_score_object_str_space

    def test_correct_ordering(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        limit = 10

        def to_datetime(string_timestamp):
            return dt.fromisoformat(string_timestamp)

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}?limit={limit}",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()

        assert response.status_code == 200

        is_sorted = all(
            to_datetime(response_data["items"][i]["last_score_timestamp"])
            <= to_datetime(response_data["items"][i + 1]["last_score_timestamp"])
            for i in range(len(response_data) - 1)
        )

        assert is_sorted, "The scores are not in order"

    def test_get_historical_score_filter_by_address(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        address = passport_holder_addresses[0]["address"]

        event_object = list(Event.objects.all())

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"address": address},
        )

        response_data = response.json()
        assert response.status_code == 200
        assert len(response_data["items"]) == 1
        assert response_data["items"][0]["address"] == address.lower()

    def test_get_historical_score_filter_by_address_and_timestamp(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        created_at = timezone.now() + datetime.timedelta(days=40)
        address = passport_holder_addresses[0]["address"]

        event_object = list(Event.objects.all())

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"created_at": created_at, "address": address},
        )

        response_data = response.json()
        assert response.status_code == 200
        assert len(response_data["items"]) == 1
        assert response_data["items"][0]["address"] == address

    def test_get_historical_scores_filter_by_timestamp(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        created_at = timezone.now() + datetime.timedelta(days=20)

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"created_at": created_at},
        )

        response_data = response.json()

        assert response.status_code == 200
        items = response_data["items"]

        for item in items:
            last_score_timestamp = item["last_score_timestamp"]
            assert (
                datetime.datetime.fromisoformat(last_score_timestamp) <= created_at
            ), f"Item with address {item['address']} has a created_at greater than the given timestamp!"

    def test_get_historical_scores_filter_by_timestamp_sorted(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        created_at = timezone.now() + datetime.timedelta(days=10)

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
            data={"created_at": created_at},
        )

        response_data = response.json()

        assert response.status_code == 200
        items = response_data["items"]
        for i in range(len(items) - 1):
            assert (
                items[i]["address"] >= items[i + 1]["address"]
            ), f"Item at index {i} is not sorted!"

    def test_get_historical_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()["items"]
        assert response.status_code == 200

        assert len(response_data) == 10

    def test_backported_get_historical_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        v1_base_url = self.base_url.replace("/v2", "")
        response = client.get(
            f"{v1_base_url}/score/{scorer_community.id}/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()["items"]
        assert response.status_code == 200

        assert len(response_data) == 10

    def test_errors_getting_historical_scores(
        self,
        scorer_api_key,
        passport_holder_addresses,
        scorer_community,
        paginated_scores,
    ):
        client = Client()
        response = client.get(
            f"{self.base_url}/score/8/history",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()
        assert response_data == {"detail": "No Community matches the given query."}

        client = Client()
        response = client.get(
            f"{self.base_url}/score/{scorer_community.id}/histor",
            HTTP_AUTHORIZATION="Token " + scorer_api_key,
        )

        response_data = response.json()
        assert response_data == {"detail": "Unable to get score for provided scorer."}
