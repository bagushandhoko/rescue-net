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
    profiles,
    public,
    queue,
)

for _module in (common, chat, context, keys, profiles, public, queue,):
    globals().update({k: v for k, v in vars(_module).items() if not k.startswith("__")})
del _module

# Analisis AI Lanjutan (Suri 2026-11-16): diteruskan lewat api_ai karena nginx hanya meneruskan rescue_net.api_*.
from rescue_net.ai.analysis import (  # noqa: E402,F401
    sitrep_ai, tanya_berujukan, analisis_foto, rencana_kirim,
    triase_laporan, prakiraan_stok, dampak_gempa, cek_kejanggalan,
    daftar_laporan_ai, baca_laporan_ai,
)
