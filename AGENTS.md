# AGENTS.md

The rules for any agent (Codex, Claude, others) working in this repo live in **`CLAUDE.md`** — it is the single
source of truth. Read it first, including the ADRs it lists under "Wajib dibaca" (`docs/adr/`), then
`docs/NEXT_STEPS.md` to see which phase is active and `HANDOVER.md` for current status.

Never run tests, seeds, cleanup or experimental migrates on production; never start a new phase without an
explicit order from the owner. Do not duplicate or override rules here — change `CLAUDE.md` instead.
