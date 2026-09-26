"""Frontend bridge API — compatibility layer.

The code lives in `rescue_net/frontend_bridge/` (one module per sub-domain). Every
name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_frontend_bridge.<name>`) and existing imports keep working; whitelisting
is attached to the function objects, so the old paths stay callable.
"""

from rescue_net.frontend_bridge import (  # noqa: F401
    common,
    consolidation,
    map_evidence,
    misc,
    reports,
    resources,
    verification,
)

for _module in (common, consolidation, map_evidence, misc, reports, resources, verification,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
