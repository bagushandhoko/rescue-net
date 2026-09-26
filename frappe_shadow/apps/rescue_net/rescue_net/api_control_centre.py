"""Control Centre API — compatibility layer.

The code lives in `rescue_net/control_centre/` (one module per sub-domain).
Every name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_control_centre.posko_detail`, …) and existing imports
(`from rescue_net.api_control_centre import _my_posko_names`) keep working.
Whitelisting is attached to the function objects, so the old paths stay
callable exactly as before.
"""

from rescue_net.control_centre import (  # noqa: F401
    bencana_aktif,
    common,
    critical,
    distribusi,
    kpi,
    map_evidence,
    org,
    posko,
)

for _module in (common, critical, map_evidence, posko, kpi, bencana_aktif, distribusi, org):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
