import asyncio
import json
from typing import Dict, List, Tuple

import aiohttp
from django.conf import settings
from django_ratelimit.exceptions import Ratelimited
from eth_utils.address import to_checksum_address
from ninja import Schema
from ninja_extra import NinjaExtraAPI
from ninja_extra.exceptions import APIException

import api_logging as logging
from registry.api.utils import aapi_key, check_rate_limit, is_valid_address
from registry.exceptions import InvalidAddressException
from scorer.settings.model_config import MODEL_AGGREGATION_NAMES

log = logging.getLogger(__name__)

api = NinjaExtraAPI(
    urls_namespace="passport",
    title="Passport Analysis API",
    description="""
The Passport Analysis API provides a simple interface to retrieve Passport analytics.\n
This API requires an API key generated in the Scorer UI to be passed in the X-API-Key header.\n
Other endpoints documented at [/docs](/docs)
""",
)


class ScoreModel(Schema):
    score: int


@api.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return api.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


class PassportAnalysisDetails(Schema):
    models: Dict[str, ScoreModel]


class PassportAnalysisResponse(Schema):
    address: str
    details: PassportAnalysisDetails


class ErrorMessageResponse(Schema):
    detail: str


class BadModelNameError(APIException):
    status_code = 400
    default_detail = "Invalid model names"


class PassportAnalysisError(APIException):
    status_code = 500
    default_detail = "Error retrieving Passport analysis"


@api.get(
    "/analysis/{address}",
    auth=aapi_key,
    response={
        200: PassportAnalysisResponse,
        400: ErrorMessageResponse,
        500: ErrorMessageResponse,
    },
    summary="Retrieve Passport analysis for an Ethereum address",
    description="Retrieve Passport analysis for an Ethereum address, currently consisting of the ETH activity model humanity score (0-100, higher is more likely human).",
    tags=["Passport Analysis"],
)
async def get_analysis(
    request, address: str, model_list: str = None
) -> PassportAnalysisResponse:
    check_rate_limit(request)
    return await handle_get_analysis(address, model_list)


async def fetch(session, url, data):
    headers = {"Content-Type": "application/json"}
    async with session.post(url, data=json.dumps(data), headers=headers) as response:
        return await response.json()


async def fetch_all(urls, payload):
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in urls:
            task = asyncio.ensure_future(fetch(session, url, payload))
            tasks.append(task)
        responses = await asyncio.gather(*tasks)
        return responses


async def handle_get_analysis(
    address: str,
    model_list: str = None,
    only_one_model=None,
) -> PassportAnalysisResponse:
    only_one_model = (
        only_one_model if only_one_model is not None else settings.ONLY_ONE_MODEL
    )
    # Set default in case nothing was selected by the user
    if not model_list or model_list.strip() == "":
        model_list = settings.MODEL_ENDPOINTS_DEFAULT

    models = list(set([model.strip() for model in model_list.split(",")]))

    if not is_valid_address(address):
        raise InvalidAddressException()

    if only_one_model and len(models) > 1:
        raise BadModelNameError(
            detail="Currently, only one model name can be provided at a time"
        )

    if len(models) == 0 or models[0] == "":
        models = ""
        raise BadModelNameError(detail="No model names provided")

    bad_models = set(models) - set(settings.MODEL_ENDPOINTS.keys())
    if bad_models:
        raise BadModelNameError(
            detail=f"Invalid model name(s): {', '.join(bad_models)}. Must be one of {', '.join(settings.MODEL_ENDPOINTS.keys())}"
        )

    # The cache historically uses checksummed addresses, need to do this for consistency
    checksummed_address = to_checksum_address(address)

    try:
        non_aggregate_models = list(set(models) - {settings.AGGREGATE_MODEL_NAME})
        if non_aggregate_models:
            responses_data = await get_model_responses(
                non_aggregate_models, checksummed_address
            )
            model_responses = list(zip(non_aggregate_models, responses_data))
        else:
            model_responses = []

        if settings.AGGREGATE_MODEL_NAME in models:
            aggregate_response = await get_aggregate_model_response(
                checksummed_address, model_responses
            )
            model_responses.append((settings.AGGREGATE_MODEL_NAME, aggregate_response))

        ret = PassportAnalysisResponse(
            address=address,
            details=PassportAnalysisDetails(models={}),
        )

        for model, response in model_responses:
            ret.details.models[model] = ScoreModel(
                score=response.get("data", {}).get("human_probability", 0)
            )

        return ret
    except Exception:
        log.error("Error retrieving Passport analysis", exc_info=True)
        raise PassportAnalysisError()


async def get_aggregate_model_response(
    checksummed_address: str, prefetched_responses: List[Tuple[str, Dict]]
):
    model_responses = await get_submodel_responses_for_aggregate(
        checksummed_address, prefetched_responses
    )

    payload = {
        "address": checksummed_address,
        "data": {},
    }

    for model, response in model_responses:
        data = response.get("data", {})
        score = data.get("human_probability", 0)
        num_transactions = data.get("n_transactions", 0)
        model_key = MODEL_AGGREGATION_NAMES[model]

        payload["data"][f"score_{model_key}"] = score
        payload["data"][f"txs_{model_key}"] = num_transactions

    url = settings.MODEL_ENDPOINTS[settings.AGGREGATE_MODEL_NAME]

    return (await fetch_all([url], payload))[0]


async def get_submodel_responses_for_aggregate(
    checksummed_address: str, prefetched_responses: List[Tuple[str, Dict]]
):
    relevant_prefetched_responses = [
        (model, response)
        for model, response in prefetched_responses
        if model in MODEL_AGGREGATION_NAMES.keys()
    ]

    prefetched_models = [model for model, _ in relevant_prefetched_responses]

    additional_models = list(MODEL_AGGREGATION_NAMES.keys() - prefetched_models)

    additional_responses_data = await get_model_responses(
        additional_models, checksummed_address
    )

    additional_model_responses = list(zip(additional_models, additional_responses_data))

    return relevant_prefetched_responses + additional_model_responses


async def get_model_responses(models: List[str], checksummed_address: str):
    urls = [settings.MODEL_ENDPOINTS[model] for model in models]

    payload = {"address": checksummed_address}
    return await fetch_all(urls, payload)
