from ninja import Schema
from registry.api.schema import ErrorMessageResponse
from typing import Optional
from humps import camelize

ErrorMessageResponse = ErrorMessageResponse


class ScorerSchema(Schema):
    weights: dict


def to_camel(string):
    return camelize(string)


class CustomizationSchema(Schema):
    class Config:
        alias_generator = to_camel
        allow_population_by_field_name = True

    # General
    path: Optional[str] = None
    scorer: ScorerSchema

    # CustomizationTheme
    customization_background_1: Optional[str] = None
    customization_background_2: Optional[str] = None
    customization_foreground_1: Optional[str] = None

    # Logo
    logo_image: Optional[str] = None
    logo_caption: Optional[str] = None
    logo_background: Optional[str] = None

    # Body
    body_main_text: Optional[str] = None
    body_sub_text: Optional[str] = None
    body_action_text: Optional[str] = None
    body_action_url: Optional[str] = None
