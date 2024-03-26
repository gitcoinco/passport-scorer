import api_logging as logging
from ninja_extra import NinjaExtraAPI, status
from ninja_extra.exceptions import APIException
from tos.models import Tos, TosAcceptanceProof
from tos.schema import TosAccepted, TosSigned, TosToSign
from trusta_labs.api import CgrantsApiKey

secret_key = CgrantsApiKey()

log = logging.getLogger(__name__)

api = NinjaExtraAPI(urls_namespace="tos")


def check_tos_accepted(tos_type: str, address: str) -> TosAccepted:
    return TosAccepted(
        accepted=TosAcceptanceProof.has_accepted(address.lower(), tos_type)
    )


def get_tos_to_sign(tos_type: str, address: str) -> TosToSign:
    text, nonce = Tos.get_message_with_nonce(tos_type)
    return TosToSign(text=text, nonce=nonce)


def accept_tos(payload: TosSigned) -> None:
    if Tos.accept(payload.tos_type, payload.nonce, payload.signature):
        return
    raise APIException(
        "Failed to process the tos acceptance proof", status.HTTP_400_BAD_REQUESTÍ
    )
