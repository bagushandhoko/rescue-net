"""Logistics API — compatibility layer.

The code lives in `rescue_net/logistics/` (one module per sub-domain). Every
name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_logistics.<name>`) and existing imports keep working; whitelisting
is attached to the function objects, so the old paths stay callable.
"""

from rescue_net.logistics import (  # noqa: F401
    common,
    flows,
    guest,
    item_groups,
    needs_offers,
    receipts,
    transport,
    user_aid,
)

for _module in (common, flows, guest, item_groups, needs_offers, receipts, transport, user_aid,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
