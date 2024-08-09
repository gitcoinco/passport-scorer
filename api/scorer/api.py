# Update the following description:
# FROM: The V1 API docs are available at /v1/docs
# TO: Useful links:
# Developer Portal
# Developer docs
# Passport API V1 playground -- To be retired on April 4th, 2024
# Fix formatting for the new historical endpoint's description.
"""
The scorer API module
"""

from typing import List, Optional

from django_ratelimit.exceptions import Ratelimited
from ninja import NinjaAPI
from ninja.openapi.schema import OpenAPISchema
from ninja.operation import Operation
from ninja.types import DictStrAny

from ceramic_cache.api.v1 import router as ceramic_cache_router_v1
from passport_admin.api import router as passport_admin_router
from registry.api.v1 import feature_flag_router
from registry.api.v1 import router as registry_router_v1
from registry.api.v2 import internal_router
from registry.api.v2 import router as registry_router_v2


###############################################################################
# The following constructs will override the default OpenAPI schema generation
# The purpose if to enable adding a custom name to the security schema defined
# by an async function used in an async api.
# The default NinjaAPI implementation will use the name of the class or
# entity (which in case of a function is `function`), hence creating confusion
# (duplicate securitySchema Types) in the generated OpenAPI live docs.
# Our implementation will use the attribute `openapi_security_schema_name` of
# the auth object if it exists (this is our customisation), otherwise it will use
#  the class name (which is what NinjaAPI does right now).
###############################################################################
class ScorerOpenAPISchema(OpenAPISchema):
    def operation_security(self, operation: Operation) -> Optional[List[DictStrAny]]:
        if not operation.auth_callbacks:
            return None
        result = []
        for auth in operation.auth_callbacks:
            if hasattr(auth, "openapi_security_schema"):
                scopes: List[DictStrAny] = []  # TODO: scopes
                name = (
                    auth.openapi_security_schema_name
                    if hasattr(auth, "openapi_security_schema_name")
                    else auth.__class__.__name__
                )
                result.append({name: scopes})  # TODO: check if unique
                self.securitySchemes[name] = auth.openapi_security_schema  # type: ignore
        return result


def scorer_get_schema(api: "NinjaAPI", path_prefix: str = "") -> ScorerOpenAPISchema:
    openapi = ScorerOpenAPISchema(api, path_prefix)
    return openapi


class ScorerApi(NinjaAPI):
    def get_openapi_schema(self, path_prefix: Optional[str] = None) -> OpenAPISchema:
        if path_prefix is None:
            path_prefix = self.root_path
        return scorer_get_schema(api=self, path_prefix=path_prefix)


###############################################################################
# End of customisinz securitySchema for OpenAPI
###############################################################################


registry_api_v1 = ScorerApi(
    urls_namespace="registry",
    title="Passport API Playground.",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/v1/openapi.json",
    description="""
The V2 (beta) API docs are available at [/v2/docs](/v2/docs)\n
The Passport Analysis endpoint is documented at [/passport/docs](/passport/docs)
""",
)
registry_api_v2 = ScorerApi(
    urls_namespace="registry_v2",
    title="Passport API Playground.",
    version="2.0.0 (beta)",
    docs_url="/v2/docs",
    openapi_url="/v2/openapi.json",
    description="""
Useful links:\n
[Developer Portal](https://scorer.gitcoin.co/)\n
[Developer docs](https://docs.passport.gitcoin.co/)\n
[Passport API V1 playground](/docs) -- To be retired on April 4th, 2024
[Passport Analysis API playground](/passport/docs)
""",
)


@registry_api_v1.exception_handler(Ratelimited)
def service_unavailable(request, _):
    return registry_api_v1.create_response(
        request,
        {"detail": "You have been rate limited!"},
        status=429,
    )


registry_api_v1.add_router("/registry/", registry_router_v1, tags=["Passport API."])

registry_api_v2.add_router("/registry/v2", registry_router_v2, tags=["Passport API."])

feature_flag_api = NinjaAPI(urls_namespace="feature")
feature_flag_api.add_router("", feature_flag_router)


ceramic_cache_api_v1 = NinjaAPI(urls_namespace="ceramic-cache", docs_url=None)
ceramic_cache_api_v1.add_router("", ceramic_cache_router_v1)


passport_admin_api = NinjaAPI(urls_namespace="passport-admin", docs_url=None)
passport_admin_api.add_router("", passport_admin_router)

internal_api = NinjaAPI(urls_namespace="internal", docs_url=None)
internal_api.add_router("", internal_router)


apis = [
    registry_api_v1,
    registry_api_v2,
    ceramic_cache_api_v1,
    passport_admin_api,
]
