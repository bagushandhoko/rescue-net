"""Resource tools API — compatibility layer.

The code lives in `rescue_net/resource_tools/` (one module per sub-domain). Every
name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_resource_tools.<name>`) and existing imports keep working; whitelisting
is attached to the function objects, so the old paths stay callable.
"""

from rescue_net.resource_tools import (  # noqa: F401
    boards,
    common,
    resources,
    work_objects,
)

for _module in (common, boards, resources, work_objects,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
