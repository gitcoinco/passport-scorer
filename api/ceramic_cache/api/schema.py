"""Ceramic Cache API Schema"""

from typing import Any, Dict, List, Optional

from ninja_schema import Schema
from registry.api.v1 import DetailedScoreResponse

from ..models import CeramicCache


class CacheStampPayload(Schema):
    address: Optional[str]
    provider: str
    stamp: Any


class DeleteStampPayload(Schema):
    address: Optional[str]
    provider: str


class CachedStampResponse(Schema):
    id: int
    address: str
    provider: str
    stamp: Any


class GetStampResponse(Schema):
    success: bool
    stamps: List[CachedStampResponse]


class GetStampsWithScoreResponse(GetStampResponse):
    score: DetailedScoreResponse


class CacaoVerifySubmit(Schema):
    issuer: str
    signatures: List[Dict]
    payload: str
    nonce: str
    cid: List[int]
    cacao: List[int]


class AccessTokenResponse(Schema):
    access: str


class ComposeDBStatusPayload(Schema):
    id: str
    compose_db_save_status: CeramicCache.ComposeDBSaveStatus
    compose_db_stream_id: Optional[str]


class ComporeDBStatusResponse(Schema):
    updated: List[int]


class CalcScorePayload(Schema):
    alternate_scorer_id: Optional[int]
