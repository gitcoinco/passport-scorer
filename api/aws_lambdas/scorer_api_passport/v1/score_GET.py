"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    authenticate_and_get_address,
    format_response,
    with_request_exception_handling,
)
from ceramic_cache.api.v1 import handle_get_ui_score


@with_request_exception_handling
def handler(event, context):
    address = authenticate_and_get_address(event)
    alternate_scorer_id = event.get("queryStringParameters", {}).get(
        "alternate_scorer_id", None
    )

    return format_response(handle_get_ui_score(address, alternate_scorer_id))
