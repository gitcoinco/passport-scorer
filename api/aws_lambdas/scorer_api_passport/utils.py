"""
This module provides utils to manage Passport API requests in AWS Lambda.
"""

import json

from aws_lambdas.utils import *

logger = logging.getLogger(__name__)

from ceramic_cache.api.v1 import JWTDidAuthentication

auth = JWTDidAuthentication()


def authenticate_and_get_address(event) -> str:
    token = get_token_from_event(event)
    valid_token = auth.get_validated_token(token)
    did = valid_token["did"]
    return did.split(":")[-1]


def get_token_from_event(event) -> str:
    logger.info("headers %s" % json.dumps(event.get("headers", {})))

    return event.get("headers", {}).get("authorization", "").split(" ")[-1]


def parse_body(event):
    if event["isBase64Encoded"]:
        body = json.loads(base64.b64decode(event["body"]).decode("utf-8"))
    elif "body" in event and event["body"]:
        body = json.loads(event["body"])
    else:
        body = {}

    return body
