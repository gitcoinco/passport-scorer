import random
import string
from datetime import datetime, timezone
from typing import Dict, List, Optional, cast

import api_logging as logging
from account.models import Account, AccountAPIKey, Community, Nonce, Customization
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from ipware import get_client_ip
from ninja import ModelSchema, Schema
from ninja_extra import NinjaExtraAPI, status
from ninja_extra.exceptions import APIException
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.schema import RefreshToken
from scorer_weighted.models import (
    BinaryWeightedScorer,
    WeightedScorer,
    get_default_weights,
)
from siwe import SiweMessage, siwe

from .deduplication import Rules

log = logging.getLogger(__name__)

api = NinjaExtraAPI(urls_namespace="account")


class SiweVerifySubmit(Schema):
    message: dict
    signature: str


CHALLENGE_STATEMENT = "I authorize the passport scorer.\n\nnonce:"


# Returns a random username to be used in the challenge
def get_random_username():
    return "".join(random.choice(string.ascii_letters) for i in range(32))


class TokenObtainPairOutSchema(Schema):
    refresh: str
    access: str


class UserSchema(Schema):
    first_name: str
    email: str


class MyTokenObtainPairOutSchema(Schema):
    refresh: str
    access: str
    user: UserSchema


class UnauthorizedException(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = "Unauthorized"


class ApiKeyDuplicateNameException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "An API Key with this name already exists"


class TooManyKeysException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You have already created 5 API Keys"


class TooManyCommunitiesException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You have already created 5 Communities"


class CommunityExistsException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A community with this name already exists"


class CommunityExistsExceptionExternalId(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "A community with this external id already exists"


class CommunityHasNoNameException(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A community must have a name"


class CommunityHasNoDescriptionException(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A community must have a description"


class CommunityHasNoBodyException(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A community must have a name and a description"


class SameCommunityNameException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You've entered the same community name"


class SameCommunityDescriptionException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "You've entered the same community description"


class ScorerTypeDoesNotExistException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The scorer type does not exist"


class FailedVerificationException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize account"


class InvalidDomainException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to authorize requests from this domain"


class InvalidNonceException(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Unable to verify the provided nonce"


class UIAuth(JWTAuth):
    def authenticate(self, request, token):
        token = self.get_validated_token(token)
        user = self.get_user(token)
        client_ip = get_client_ip(request)[0]

        # if the user's current ip is different from the ip address in the token claim
        if client_ip != token.get("ip_address"):
            raise UnauthorizedException("IP address has changed")

        request.user = user
        return user


# API endpoint for nonce
@api.get("/nonce")
def nonce(request):
    nonce = Nonce.create_nonce(ttl=300)

    # CORS (specific domains, not *) for the /account endpoints
    # and fetch(url, {credentials: "include"}) in the frontend
    # must be configured in order to facilitate sessions

    # request.session["nonce"] = nonce.nonce

    return {"nonce": nonce.nonce}


class AccountApiSchema(ModelSchema):
    class Config:
        model = AccountAPIKey
        model_fields = ["name", "id", "prefix"]

    api_key: Optional[str] = None


class CommunityApiSchema(ModelSchema):
    class Config:
        model = Community
        model_fields = ["name", "description", "id", "created_at", "use_case"]


@api.post("/verify", response=TokenObtainPairOutSchema)
def submit_signed_challenge(request, payload: SiweVerifySubmit):
    payload.message["chain_id"] = payload.message["chainId"]
    payload.message["issued_at"] = payload.message["issuedAt"]

    if not Nonce.use_nonce(payload.message["nonce"]):
        raise InvalidNonceException()

    try:
        message: SiweMessage = SiweMessage(payload.message)
        verifyParams = {
            "signature": payload.signature,
            # See note in /nonce function above
            # "nonce": request.session["nonce"],
        }

        message.verify(**verifyParams)
    except siwe.DomainMismatch:
        raise InvalidDomainException()
    except siwe.VerificationError:
        raise FailedVerificationException()

    address_lower = payload.message["address"]

    try:
        account = Account.objects.get(address=address_lower)
    except Account.DoesNotExist:
        user = get_user_model().objects.create_user(username=get_random_username())
        user.save()
        account = Account(address=address_lower, user=user)
        account.save()

    refresh = RefreshToken.for_user(account.user)

    # include IP address in JWT claims
    refresh["ip_address"] = get_client_ip(request)[0]

    refresh = cast(RefreshToken, refresh)

    return {"ok": True, "refresh": str(refresh), "access": str(refresh.access_token)}


class TokenValidationRequest(Schema):
    token: str


class TokenValidationResponse(Schema):
    exp: str = ""


@api.post("/validate_token", response=TokenValidationResponse)
def validate_token(request, payload: TokenValidationRequest):
    uiAuth = UIAuth()
    token = uiAuth.get_validated_token(payload.token)
    client_ip = get_client_ip(request)[0]

    # if the user's current ip is different from the ip address in the token claim
    if client_ip != token.get("ip_address"):
        raise UnauthorizedException("IP address has changed")

    return {"exp": token["exp"]}


class APIKeyName(Schema):
    name: str


@api.post("/api-key", auth=UIAuth(), response=AccountApiSchema)
def create_api_key(request, payload: APIKeyName):
    try:
        account = request.user.account
        if AccountAPIKey.objects.filter(account=account).count() >= 5:
            raise TooManyKeysException()

        if AccountAPIKey.objects.filter(name=payload.name).count() == 1:
            raise ApiKeyDuplicateNameException()

        key_name = payload.name

        api_key, key = AccountAPIKey.objects.create_key(account=account, name=key_name)
    except Account.DoesNotExist:
        raise UnauthorizedException()

    return {
        "id": api_key.id,
        "name": api_key.name,
        "prefix": api_key.prefix,
        "api_key": key,
    }


@api.get("/api-key", auth=UIAuth(), response=List[AccountApiSchema])
def get_api_keys(request):
    try:
        account = request.user.account
        api_keys = AccountAPIKey.objects.filter(account=account).all()

    except Account.DoesNotExist:
        raise UnauthorizedException()
    return api_keys


@api.patch("/api-key/{path:api_key_id}", auth=UIAuth())
def patch_api_keys(request, api_key_id, payload: APIKeyName):
    try:
        api_key = get_object_or_404(
            AccountAPIKey, id=api_key_id, account=request.user.account
        )

        if payload.name:
            api_key.name = payload.name
            api_key.save()

    except Account.DoesNotExist:
        raise UnauthorizedException()

    return {"ok": True}


@api.delete("/api-key/{path:api_key_id}", auth=UIAuth())
def delete_api_key(request, api_key_id):
    try:
        api_key = get_object_or_404(
            AccountAPIKey, id=api_key_id, account=request.user.account
        )
        api_key.delete()
    except Account.DoesNotExist:
        raise UnauthorizedException()
    return {"ok": True}


def health(request):
    return HttpResponse("Ok")


class CommunitiesPayload(Schema):
    name: str
    description: str
    use_case: str
    rule: str = Rules.LIFO.value
    scorer: str


def create_community_for_account(
    account,
    name,
    description,
    limit,
    scorer,
    use_case,
    rule,
    external_scorer_id=None,
):
    account_communities = Community.objects.filter(account=account, deleted_at=None)

    if account_communities.count() >= limit:
        raise TooManyCommunitiesException()

    if account_communities.filter(name=name).exists():
        raise CommunityExistsException()

    if len(name) == 0:
        raise CommunityHasNoNameException()

    if (
        external_scorer_id
        and account_communities.filter(external_scorer_id=external_scorer_id).exists()
    ):
        raise CommunityExistsExceptionExternalId()

    # Create the scorer
    if scorer == "WEIGHTED_BINARY":
        scorer = BinaryWeightedScorer(type="WEIGHTED_BINARY")
    else:
        scorer = WeightedScorer()

    scorer.save()

    # Create the community
    community = Community.objects.create(
        account=account,
        name=name,
        description=description,
        use_case=use_case,
        rule=rule,
        scorer=scorer,
        external_scorer_id=external_scorer_id,
    )

    return community


@api.post("/communities", auth=UIAuth())
def create_community(request, payload: CommunitiesPayload):
    try:
        account = request.user.account
        if payload is None:
            raise CommunityHasNoBodyException()

        if len(payload.description) == 0:
            raise CommunityHasNoDescriptionException()

        create_community_for_account(
            account,
            payload.name,
            payload.description,
            settings.USER_COMMUNITY_CREATION_LIMIT,
            payload.scorer,
            payload.use_case,
            payload.rule,
        )

        return {"ok": True}

    except Account.DoesNotExist:
        raise UnauthorizedException()


@api.get("/communities", auth=UIAuth(), response=List[CommunityApiSchema])
def get_communities(request):
    try:
        account = request.user.account
        communities = (
            Community.objects.filter(account=account, deleted_at=None)
            .order_by("id")
            .all()
        )

    except Account.DoesNotExist:
        raise UnauthorizedException()
    return communities


class APIKeyId(Schema):
    id: str


class CommunitiesUpdatePayload(Schema):
    name: str
    description: str
    use_case: str


@api.put("/communities/{community_id}", auth=UIAuth())
def update_community(request, community_id, payload: CommunitiesUpdatePayload):
    try:
        account = request.user.account
        community = get_object_or_404(
            Community, id=community_id, account=account, deleted_at=None
        )

        # Check for duplicates in other communities within the same account
        if (
            Community.objects.filter(
                name=payload.name, account=account, deleted_at=None
            )
            .exclude(id=community_id)
            .exists()
        ):
            raise CommunityExistsException()

        community.name = payload.name
        community.description = payload.description
        community.use_case = payload.use_case

        community.save()

    except Account.DoesNotExist:
        raise UnauthorizedException()

    return {"ok": True}


class CommunitiesPatchPayload(Schema):
    name: str = None
    description: str = None


@api.patch("/communities/{community_id}", auth=UIAuth())
def patch_community(request, community_id, payload: CommunitiesPatchPayload):
    try:
        account = request.user.account
        community = get_object_or_404(
            Community, id=community_id, account=account, deleted_at=None
        )

        if payload.name:
            community.name = payload.name
            # Check for duplicates in other communities within the same account
            if (
                Community.objects.filter(
                    name=payload.name, account=account, deleted_at=None
                )
                .exclude(id=community_id)
                .exists()
            ):
                raise CommunityExistsException()

        if payload.description:
            community.description = payload.description

        community.save()
    except Account.DoesNotExist:
        raise UnauthorizedException()

    return {"ok": True}


@api.delete("/communities/{community_id}", auth=UIAuth())
def delete_community(request, community_id):
    try:
        community = get_object_or_404(
            Community, id=community_id, account=request.user.account, deleted_at=None
        )
        community.deleted_at = datetime.now(timezone.utc)
        community.save()
    except Account.DoesNotExist:
        raise UnauthorizedException()
    return {"ok": True}


class ScorersResponse(Schema):
    ok: bool
    current_scorer: str
    scorers: List[Dict[str, str]]


@api.get("/communities/{community_id}/scorers", auth=UIAuth(), response=ScorersResponse)
def get_community_scorers(request, community_id):
    try:
        community = get_object_or_404(
            Community, id=community_id, account=request.user.account, deleted_at=None
        )

        scorer = community.scorer
        current_scorer = scorer.type
        scorers = [{"id": i[0], "label": i[1]} for i in scorer.Type.choices]

    except Community.DoesNotExist:
        raise UnauthorizedException()
    return {
        "ok": True,
        "current_scorer": current_scorer,
        "scorers": scorers,
    }


class ScorerId(Schema):
    scorer_type: str


@api.put("/communities/{community_id}/scorers", auth=UIAuth())
def update_community_scorers(request, community_id, payload: ScorerId):
    try:
        community = get_object_or_404(
            Community, id=community_id, account=request.user.account, deleted_at=None
        )

        if payload.scorer_type not in community.scorer.Type:
            raise ScorerTypeDoesNotExistException()

        # this is all too dependent on there being only the two
        # scorer types, WeightedScorer and BinaryWeightedScorer
        # Should probably do this a bit differently, but we should
        # have a larger conversation on how we want to persist this
        # data and separate scoring classes first

        if community.scorer and getattr(community.scorer, "weightedscorer", None):
            oldWeights = community.scorer.weightedscorer.weights
        elif community.scorer and getattr(
            community.scorer, "binaryweightedscorer", None
        ):
            oldWeights = community.scorer.binaryweightedscorer.weights
        else:
            oldWeights = None

        if payload.scorer_type == community.scorer.Type.WEIGHTED_BINARY:
            # Threshold should be passed in as part of the payload instead of hardcoded
            newScorer = BinaryWeightedScorer()
        else:
            newScorer = WeightedScorer()

        # Weights should likely be passed in too, or use defaults, or something
        if oldWeights:
            newScorer.weights = oldWeights

        newScorer.type = payload.scorer_type

        newScorer.save()

        oldScorer = community.scorer

        community.scorer = newScorer

        community.save()

        # Do we want to hang on to this, maybe associate it with the Scores?
        # Or, do we want to disallow modifying scoring rules after scores have
        # been created? Or store a date on the score, and a scoringRulesLastUpdated
        # date on the community, and compare the two when reporting? We need to do
        # one of those things to avoid showing scores from a previous scorer as fully approved
        # => for now let us just hang on to this
        oldScorer.delete()

    except Community.DoesNotExist:
        raise UnauthorizedException()
    return {"ok": True}


@api.get("/customization/{dashboard_path}/", auth=None)
def get_account_customization(request, dashboard_path: str):
    try:
        customization = Customization.objects.get(path=dashboard_path)
        scorer = customization.scorer.scorer

        weights = get_default_weights

        if scorer and getattr(scorer, "weightedscorer", None):
            weights = scorer.weightedscorer.weights
        elif scorer and getattr(scorer, "binaryweightedscorer", None):
            weights = scorer.binaryweightedscorer.weights

        return dict(
            key=customization.path,
            useCustomDashboardPanel=customization.use_custom_dashboard_panel,
            customizationTheme={
                "colors": {
                    "customizationBackground1": customization.customization_background_1,
                    "customizationBackground2": customization.customization_background_2,
                    "customizationForeground1": customization.customization_foreground_1,
                }
            },
            dashboardPanel={
                "logo": {
                    "image": customization.logo_image,
                    "caption": customization.logo_caption,
                    "background": customization.logo_background,
                },
                "body": {
                    "mainText": customization.body_main_text,
                    "subText": customization.body_sub_text,
                    "action": {
                        "text": customization.body_action_text,
                        "url": customization.body_action_url,
                    },
                },
            },
            scorer={
                "weights": weights,
                "id": customization.scorer.id,
            },
        )

    except Customization.DoesNotExist:
        raise APIException("Customization not found", status.HTTP_404_NOT_FOUND)
