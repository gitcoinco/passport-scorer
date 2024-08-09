from datetime import datetime
from typing import List, Optional

from django.db.models import Q
from ninja import Router, Schema
from ninja.security import APIKeyHeader

import api_logging as logging

# --- Deduplication Modules
from account.models import Community
from registry.admin import get_s3_client
from registry.api import common, v1
from registry.api.schema import (
    CursorPaginatedHistoricalScoreResponse,
    CursorPaginatedScoreResponse,
    CursorPaginatedStampCredentialResponse,
    DetailedScoreResponse,
    ErrorMessageResponse,
    SigningMessageResponse,
    StampDisplayResponse,
    SubmitPassportPayload,
)
from registry.api.utils import (
    ApiKey,
    check_rate_limit,
    track_apikey_usage,
    with_read_db,
)
from registry.exceptions import (
    InvalidAddressException,
    InvalidLimitException,
    api_get_object_or_404,
)
from registry.models import BatchModelScoringRequest, BatchRequestStatus, Score
from registry.utils import (
    decode_cursor,
    encode_cursor,
    get_cursor_query_condition,
    reverse_lazy_with_query,
)
from scorer import settings
from scorer.settings import (
    BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER,
    BULK_SCORE_REQUESTS_BUCKET_NAME,
)

log = logging.getLogger(__name__)

router = Router()


@router.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Retrieve a signing message",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
def signing_message(request) -> SigningMessageResponse:
    return v1.signing_message(request)


@router.post(
    "/submit-passport",
    auth=v1.aapi_key,
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Submit an Ethereum address to the Scorer",
    description="""Use this API to submit your passport for scoring.\n
This API will return a `DetailedScoreResponse` structure with status **PROCESSING** immediatly while your passport is being pulled from storage and the scoring algorithm is run.\n
You need to check for the status of the operation by calling the `/score/{int:scorer_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
""",
)
async def a_submit_passport(
    request, payload: SubmitPassportPayload
) -> DetailedScoreResponse:
    return await v1.a_submit_passport(request, payload)


@router.get(
    "/score/{int:scorer_id}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve the Passport scores for all submitted addresses",
    description="""Use this endpoint to fetch the scores for all addresses that are associated with a scorer\n
This endpoint will return a `CursorPaginatedScoreResponse`.\n
\n

Note: results will be sorted ascending by `["last_score_timestamp", "id"]`
""",
)
@track_apikey_usage(track_response=False)
def get_scores(
    request,
    scorer_id: int,
    address: Optional[str] = None,
    last_score_timestamp__gt: str = "",
    last_score_timestamp__gte: str = "",
    token: str = None,
    limit: int = 1000,
) -> CursorPaginatedScoreResponse:
    check_rate_limit(request)

    if limit > 1000:
        raise InvalidLimitException()

    # Get community object
    user_community = api_get_object_or_404(
        Community, id=scorer_id, account=request.auth
    )
    try:
        base_query = (
            with_read_db(Score)
            .filter(passport__community__id=user_community.id)
            .select_related("passport")
        )

        filter_condition = Q()
        field_ordering = None
        cursor = decode_cursor(token) if token else None
        sort_fields = ["last_score_timestamp", "id"]

        if cursor:
            cursor = decode_cursor(token)
            cursor["last_score_timestamp"] = datetime.fromisoformat(
                cursor.get("last_score_timestamp")
            )
            filter_condition, field_ordering = get_cursor_query_condition(
                cursor, sort_fields
            )

        else:
            field_ordering = ["last_score_timestamp", "id"]

            if address:
                if not v1.is_valid_address(address):
                    raise InvalidAddressException()
                filter_condition &= Q(passport__address=address)

            if last_score_timestamp__gt:
                filter_condition &= Q(last_score_timestamp__gt=last_score_timestamp__gt)

            if last_score_timestamp__gte:
                filter_condition &= Q(
                    last_score_timestamp__gte=last_score_timestamp__gte
                )

        has_more_scores = has_prev_scores = False
        next_cursor = prev_cursor = {}

        query = base_query.filter(filter_condition).order_by(*field_ordering)
        scores = query[:limit]
        scores = list(scores)

        if cursor and cursor["d"] == "prev":
            scores.reverse()

        if scores:
            next_id = scores[-1].id
            next_lts = scores[-1].last_score_timestamp
            prev_id = scores[0].id
            prev_lts = scores[0].last_score_timestamp

            next_cursor = dict(
                d="next",
                id=next_id,
                last_score_timestamp=next_lts.isoformat(),
                address=address,
                last_score_timestamp__gt=last_score_timestamp__gt,
                last_score_timestamp__gte=last_score_timestamp__gte,
            )
            prev_cursor = dict(
                d="prev",
                id=prev_id,
                last_score_timestamp=prev_lts.isoformat(),
                address=address,
                last_score_timestamp__gt=last_score_timestamp__gt,
                last_score_timestamp__gte=last_score_timestamp__gte,
            )

            next_filter_cond, _ = get_cursor_query_condition(next_cursor, sort_fields)
            prev_filter_cond, _ = get_cursor_query_condition(prev_cursor, sort_fields)

            has_more_scores = base_query.filter(next_filter_cond).exists()
            has_prev_scores = base_query.filter(prev_filter_cond).exists()

        domain = request.build_absolute_uri("/")[:-1]

        next_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(**next_cursor), "limit": limit},
            )}"""
            if has_more_scores
            else None
        )

        prev_url = (
            f"""{domain}{reverse_lazy_with_query(
                "registry_v2:get_scores",
                args=[scorer_id],
                query_kwargs={"token": encode_cursor(**prev_cursor), "limit": limit},
            )}"""
            if has_prev_scores
            else None
        )

        response = CursorPaginatedScoreResponse(
            next=next_url, prev=prev_url, items=scores
        )

        return response

    except Exception as e:
        log.error(
            "Error getting passport scores. scorer_id=%s",
            scorer_id,
            exc_info=True,
        )
        raise e


@router.get(
    "/stamps/{str:address}",
    auth=ApiKey(),
    response={
        200: CursorPaginatedStampCredentialResponse,
        400: ErrorMessageResponse,
        401: ErrorMessageResponse,
    },
    summary="Receive Stamps verified by submitted Passports",
    description="""Use this endpoint to fetch the passport for a specific address\n
This endpoint will return a `CursorPaginatedStampCredentialResponse`.\n
""",
    # This prevents returning {metadata: None} in the response
    exclude_unset=True,
)
def get_passport_stamps(
    request,
    address: str,
    token: str = "",
    limit: int = 1000,
    include_metadata: bool = False,
) -> CursorPaginatedStampCredentialResponse:
    return v1.get_passport_stamps(request, address, token, limit, include_metadata)


@router.get(
    "/stamp-metadata",
    summary="Receive all Stamps available in Passport",
    description="""**WARNING**: This endpoint is in beta and is subject to change.""",
    auth=ApiKey(),
    response={
        200: List[StampDisplayResponse],
        500: ErrorMessageResponse,
    },
)
def stamp_display(request) -> List[StampDisplayResponse]:
    return v1.stamp_display(request)


@router.get(
    "gtc-stake/{str:address}/{int:round_id}",
    summary="Retrieve GTC stake amounts from legacy staking contract",
    description="Get self and community GTC staking amounts based on address and round ID",
    auth=ApiKey(),
    response=v1.GtcEventsResponse,
)
def get_gtc_stake_legacy(request, address: str, round_id: str):
    if not v1.is_valid_address(address):
        raise InvalidAddressException()
    return v1.get_gtc_stake_legacy(request, address, round_id)


@router.get(
    common.history_endpoint["url"],
    auth=common.history_endpoint["auth"],
    response=common.history_endpoint["response"],
    summary=common.history_endpoint["summary"],
    description=common.history_endpoint["description"],
)
def get_score_history(
    request,
    scorer_id: int,
    address: Optional[str] = None,
    created_at: str = "",
    token: str = None,
    limit: int = 1000,
) -> CursorPaginatedHistoricalScoreResponse:
    if address and not v1.is_valid_address(address):
        raise InvalidAddressException()
    return common.history_endpoint["handler"](
        request, scorer_id, address, created_at, token, limit
    )


@router.get(
    "/score/{int:scorer_id}/{str:address}",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Retrieve a Passport score for one address",
    description=f"""Use this endpoint to fetch the score for a specific address that is associated with a scorer\n
This endpoint will return a `DetailedScoreResponse`. This endpoint will also return the status of the asynchronous operation that was initiated with a request to the `/submit-passport` API.\n
{v1.SCORE_TIMESTAMP_FIELD_DESCRIPTION}
""",
)
def get_score(request, address: str, scorer_id: int) -> DetailedScoreResponse:
    return v1.get_score(request, address, scorer_id)


internal_router = Router()


class DataScienceApiKey(APIKeyHeader):
    param_name = "AUTHORIZATION"

    def authenticate(self, request, key):
        if key == settings.DATA_SCIENCE_API_KEY:
            return key
        return None


data_science_auth = DataScienceApiKey()


class BatchResponse(Schema):
    created_at: str
    s3_url: Optional[str]
    status: BatchRequestStatus
    percentage_complete: int


@internal_router.get(
    "/analysis/internal",
    auth=data_science_auth,
    response={
        200: list[BatchResponse],
        400: ErrorMessageResponse,
        500: ErrorMessageResponse,
    },
    summary="Retrieve batch scoring status and result",
    description="Retrieve batch scoring status and result",
)
def get_batch_analysis_stats(request, limit: int = 10) -> list[BatchResponse]:
    requests = BatchModelScoringRequest.objects.order_by("-created_at")[:limit]
    return [
        BatchResponse(
            created_at=req.created_at.isoformat(),
            s3_url=(
                get_s3_client().generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": BULK_SCORE_REQUESTS_BUCKET_NAME,
                        "Key": f"{BULK_MODEL_SCORE_REQUESTS_RESULTS_FOLDER}/{req.s3_filename}",
                    },
                    # 24 hrs
                    ExpiresIn=60 * 60 * 24,
                )
                if req.status == BatchRequestStatus.DONE
                else None
            ),
            status=req.status,
            percentage_complete=req.progress,
        )
        for req in requests
    ]
