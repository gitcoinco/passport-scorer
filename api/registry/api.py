import logging
from decimal import Decimal
from enum import Enum
from typing import List, Optional

# --- Deduplication Modules
from account.models import AccountAPIKey, Community, Nonce
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.pagination import paginate
from ninja.security import APIKeyHeader
from ninja_extra.exceptions import APIException
from registry.models import Passport, Score
from registry.permissions import ResearcherPermission
from registry.utils import (
    get_signer,
    get_signing_message,
    permissions_required,
    reverse_lazy_with_query,
)

from .exceptions import (
    InternalServerErrorException,
    InvalidCommunityScoreRequestException,
    InvalidLimitException,
    InvalidNonceException,
    InvalidSignerException,
    Unauthorized,
    api_get_object_or_404,
)
from .tasks import score_passport

log = logging.getLogger(__name__)
# api = NinjaExtraAPI(urls_namespace="registry")
router = Router()

analytics_router = Router()


class SubmitPassportPayload(Schema):
    address: str
    community_id: int
    signature: str = ""
    nonce: str = ""


class ScoreEvidenceResponse(Schema):
    type: str
    success: bool


class ThresholdScoreEvidenceResponse(ScoreEvidenceResponse):
    rawScore: Decimal
    threshold: Decimal


class StatusEnum(str, Enum):
    processing = Score.Status.PROCESSING
    error = Score.Status.ERROR
    done = Score.Status.DONE


class DetailedScoreResponse(Schema):
    address: str
    score: Optional[str]
    status: Optional[StatusEnum]
    last_score_timestamp: Optional[str]
    evidence: Optional[ThresholdScoreEvidenceResponse]
    error: Optional[str]

    @staticmethod
    def resolve_last_score_timestamp(obj):
        if obj.last_score_timestamp:
            return obj.last_score_timestamp.isoformat()
        return None

    @staticmethod
    def resolve_address(obj):
        return obj.passport.address


class CursorPaginatedScoreResponse(Schema):
    next: Optional[str]
    items: List[DetailedScoreResponse]


class SimpleScoreResponse(Schema):
    address: str
    score: Decimal  # The score should be represented as string as it will be a decimal number


class SigningMessageResponse(Schema):
    message: str
    nonce: str


class ErrorMessageResponse(Schema):
    detail: str


class ApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        """
        The authenticate method will validate the API key:
        1. first in the X-API-Key header - this will have preceedence
        2. in the HTTP_AUTHORIZATION header if none exists in the X-API-Key header (this is for backwards compatibility)
        """
        if not key:
            # if X-API-Key was not specified in the header read the HTTP_AUTHORIZATION
            # and try to load the tey from there
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if not auth_header:
                raise Unauthorized()

            try:
                key = auth_header.split()[1]
            except:
                raise Unauthorized()

        try:
            api_key = AccountAPIKey.objects.get_from_key(key)
            user_account = api_key.account
            if user_account:
                request.user = user_account.user
                return user_account
        except AccountAPIKey.DoesNotExist:
            raise Unauthorized()


@router.get(
    "/signing-message",
    auth=ApiKey(),
    response={
        200: SigningMessageResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to get a message to sign and a nonce to use when submitting your passport for scoring.""",
)
def signing_message(_request) -> SigningMessageResponse:
    nonce = Nonce.create_nonce().nonce
    return {
        "message": get_signing_message(nonce),
        "nonce": nonce,
    }


# TODO define logic once Community model has been updated
def community_requires_signature(_):
    return False


@router.post(
    "/submit-passport",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Submit passport for scoring",
    description="""Use this API to submit your passport for scoring.\n
This API will return a `DetailedScoreResponse` structure with status **PROCESSING** immediatly while your passport is being pulled from storage and the scoring algorithm is run.\n
You need to check for the status of the operation by calling the `/score/{int:community_id}/{str:address}` API. The operation will have finished when the status returned is **DONE**
""",
)
def submit_passport(request, payload: SubmitPassportPayload) -> DetailedScoreResponse:
    address_lower = payload.address.lower()

    # Get DID from address
    # did = get_did(payload.address)
    log.debug("/submit-passport, payload=%s", payload)

    # Get community object
    user_community = get_object_or_404(
        Community, id=payload.community_id, account=request.auth
    )

    # Verify the signer
    # TODO This first condition--payload.signature--is only here for testing and
    # can be removed when community_requires_signature() is completed
    if payload.signature or community_requires_signature(user_community):
        if get_signer(payload.nonce, payload.signature).lower() != address_lower:
            raise InvalidSignerException()

        # Verify nonce
        if not Nonce.use_nonce(payload.nonce):
            log.error("Invalid nonce %s for address %s", payload.nonce, payload.address)
            raise InvalidNonceException()

    # Create an empty passport instance, only needed to be able to create a pending Score
    # The passport will be updated by the score_passport task
    db_passport, _ = Passport.objects.update_or_create(
        address=payload.address.lower(),
        community=user_community,
        defaults={
            "passport": {},  # Leave the dict empty for now
        },
    )

    # Create a score with status PROCESSING
    score, _ = Score.objects.update_or_create(
        passport_id=db_passport.id,
        defaults=dict(score=None, status=Score.Status.PROCESSING),
    )

    score_passport.delay(user_community.id, payload.address)

    return DetailedScoreResponse(
        address=score.passport.address,
        score=score.score,
        status=score.status,
        evidence=score.evidence,
        last_score_timestamp=score.last_score_timestamp.isoformat()
        if score.last_score_timestamp
        else None,
    )


@router.get(
    "/score/{int:community_id}/{str:address}",
    auth=ApiKey(),
    response={
        200: DetailedScoreResponse,
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get score for an address that is associated with a community",
    description="""Use this endpoint to fetch the score for a specific address that is associated with a community\n
This endpoint will return a `DetailedScoreResponse`. This endpoint will also return the status of the asynchronous operation that was initiated with a request to the `/submit-passport` API.\n
""",
)
def get_score(request, address: str, community_id: int) -> DetailedScoreResponse:
    # Get community object
    user_community = api_get_object_or_404(
        Community, id=community_id, account=request.auth
    )

    try:
        lower_address = address.lower()

        score = Score.objects.get(
            passport__address=lower_address, passport__community=user_community
        )
        return score
    except Exception as e:
        log.error(
            "Error getting passport scores. community_id=%s",
            community_id,
            exc_info=True,
        )
        raise InvalidCommunityScoreRequestException()


@router.get(
    "/score/{int:community_id}",
    auth=ApiKey(),
    response={
        200: List[DetailedScoreResponse],
        401: ErrorMessageResponse,
        400: ErrorMessageResponse,
        404: ErrorMessageResponse,
    },
    summary="Get scores for all addresses that are associated with a community",
    description="""Use this endpoint to fetch the scores for all addresses that are associated with a community\n
This API will return a list of `DetailedScoreResponse` objects. The endpoint supports pagination and will return a maximum of 1000 scores per request.\n
Pass a limit and offset query parameter to paginate the results. For example: `/score/1?limit=100&offset=100` will return the second page of 100 scores.\n
""",
)
@paginate(pass_parameter="pagination_info")
def get_scores(
    request, community_id: int, address: str = "", **kwargs
) -> List[DetailedScoreResponse]:
    if kwargs["pagination_info"].limit > 1000:
        raise InvalidLimitException()

    # Get community object
    user_community = api_get_object_or_404(
        Community, id=community_id, account=request.auth
    )

    try:
        scores = Score.objects.filter(
            passport__community__id=user_community.id
        ).prefetch_related("passport")

        if address:
            scores = scores.filter(passport__address=address.lower())

        return scores

    except Exception as e:
        log.error(
            "Error getting passport scores. community_id=%s",
            community_id,
            exc_info=True,
        )
        raise e


@analytics_router.get("/score/", auth=ApiKey(), response=CursorPaginatedScoreResponse)
@permissions_required([ResearcherPermission])
def get_scores_analytics(
    request, last_id: int = None, limit: int = 1000
) -> CursorPaginatedScoreResponse:
    query = Score.objects.order_by("id")

    if limit and limit > 1000:
        limit = 1000

    if last_id:
        query = query.filter(id__gt=last_id)

    if limit and len(query) >= limit:
        last_score = query[limit - 1 : limit][0]
    else:
        last_score = query.last()

    scores = query[:limit]

    next_url = (
        reverse_lazy_with_query(
            "analytics:get_scores_analytics", query_kwargs={"last_id": last_score.id}
        )
        if last_score
        else None
    )

    response = CursorPaginatedScoreResponse(next=next_url, items=scores)

    return response


@analytics_router.get(
    "/score/{int:community_id}", auth=ApiKey(), response=CursorPaginatedScoreResponse
)
@permissions_required([ResearcherPermission])
def get_scores_by_community_id_analytics(
    request,
    community_id: int,
    address: str = "",
    last_id: int = None,
    limit: int = 1000,
) -> CursorPaginatedScoreResponse:
    user_community = api_get_object_or_404(Community, id=community_id)

    query = Score.objects.order_by("id")

    if limit and limit > 1000:
        limit = 1000

    if last_id:
        query = query.filter(
            id__gt=last_id, passport__community__id=user_community.id
        ).prefetch_related("passport")
    else:
        query = query.filter(
            passport__community__id=user_community.id
        ).prefetch_related("passport")

    if address:
        query = query.filter(passport__address=address.lower())

    if limit and len(query) >= limit:
        last_score = query[limit - 1 : limit][0]
    else:
        last_score = query.last()

    scores = query[:limit]

    next_url = (
        reverse_lazy_with_query(
            "analytics:get_scores_by_community_id_analytics",
            args=[community_id],
            query_kwargs={"last_id": last_score.id},
        )
        if last_score
        else None
    )

    response = CursorPaginatedScoreResponse(next=next_url, items=scores)

    return response
