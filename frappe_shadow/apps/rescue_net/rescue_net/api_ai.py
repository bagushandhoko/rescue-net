"""AI API — compatibility layer.

The code lives in `rescue_net/ai/` (one module per sub-domain). Every
name is re-exported here so the dotted paths the frontend calls
(`rescue_net.api_ai.<name>`) and existing imports keep working; whitelisting
is attached to the function objects, so the old paths stay callable.
"""

from rescue_net.ai import (  # noqa: F401
    chat,
    common,
    context,
    keys,
    public,
)

for _module in (common, chat, context, keys, public,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module
