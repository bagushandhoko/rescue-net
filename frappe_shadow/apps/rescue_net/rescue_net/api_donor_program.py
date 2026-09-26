"""Donor program API — compatibility layer.

The code lives in `rescue_net/donor_program/` (one module per sub-domain). Every
name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_donor_program.<name>`) and existing imports keep working; whitelisting
is attached to the function objects, so the old paths stay callable.
"""

from rescue_net.donor_program import (  # noqa: F401
    board,
    common,
    programs,
    special,
)

for _module in (common, board, programs, special,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
