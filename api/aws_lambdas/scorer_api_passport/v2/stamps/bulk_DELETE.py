"""
This module provides a handler to manage API requests in AWS Lambda.
"""

from aws_lambdas.scorer_api_passport.utils import (
    authenticate_and_get_address, format_response, parse_body,
    with_request_exception_handling)
from ceramic_cache.api.v2 import DeleteStampPayload, handle_delete_stamps


@with_request_exception_handling
def handler(event, context):
    address = authenticate_and_get_address(event)
    body = parse_body(event)

    payload = [DeleteStampPayload(**p) for p in body]

    return format_response(handle_delete_stamps(address, payload))
