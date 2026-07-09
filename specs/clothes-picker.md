# Spec: clothes picker — trigger phrase shows a checklist instead of auto-running everything

## Goal

When Jacob says "find me clothes on the marketplace scout" (or similar), Claude
must NOT immediately run the full hunt. Instead Claude shows an interactive
multi-select checklist of his wardrobe items, he checks what he wants (with a
select-all option), can type in new items, and only then the search runs.

This is a Claude workflow, not scout code — no changes to scout.py or
sync_wardrobe.py. The deliverables are the procedure encoded in Claude's
memory file and documented in the vault note.

## Requirements

### R1 — Procedure content (must appear in the memory file)
The memory file `~/.claude/projects/-Users-jacoble/memory/feedback_marketplace_clothes.md`
must define this exact flow for the trigger phrase:

1. **Sync first**: run `python3 ~/marketplace-scout/sync_wardrobe.py`, then read
   the `clothes` group presets + queries from `~/marketplace-scout/config.json`
   (the checklist must reflect the CURRENT note, never a hardcoded list).
2. **Show the checklist**: one `AskUserQuestion` call with up to 4 multiSelect
   questions grouped by category (e.g. Boots / Shoes & shorts / Shirts /
   Pants & jackets). Bundle closely-related presets into single options to fit
   the 4-options-per-question limit (e.g. "Red Wing — Iron Ranger + Moc Toe").
   Every current preset must be reachable through some option.
3. **Select-all**: the first question's first option is
   "Everything — full wardrobe hunt". If checked, ignore other selections and
   run `~/marketplace-scout/scout clothes`.
4. **Custom additions**: free-text entered via the built-in "Other" field is
   (a) searched in this run as a raw query, and (b) appended as a new row to
   the best-matching Brand/Model table in the vault wardrobe note
   `20 Areas/Personal/Wardrobe — Timeless Functional Aesthetic.md` so the
   auto-sync persists it for future runs.
5. **Run**: map checked options to preset slugs and run
   `~/marketplace-scout/scout <slug...> [raw queries...] --platforms craigslist
   offerup facebook mercari depop poshmark` in the background
   (`run_in_background`), then deliver the report path when it completes.
   (Individual presets don't carry the clothes platforms — only the group
   does — so the explicit `--platforms` list is REQUIRED for picked subsets.)

### R2 — Memory index updated
The `MEMORY.md` line for the clothes trigger must say the phrase opens a
checklist picker (not that it auto-runs everything).

### R3 — Vault doc updated
`10 Projects/Marketplace Scout.md` must describe the new behavior in the
section about the trigger phrase: checklist appears, select-all available,
typed-in items get searched and added to the wardrobe note automatically.

### R4 — No scout code changes
`scout.py`, `sync_wardrobe.py`, and `config.json` are untouched by this spec
(git diff / file mtimes may not show modifications from this build).

## Verification
- Memory file contains: the sync-first step, the AskUserQuestion/multiSelect
  instruction, the select-all rule, the Other-field add-to-note rule, and the
  exact `--platforms` list requirement.
- MEMORY.md line mentions the picker.
- Vault doc mentions the checklist behavior.
- A live demo of the picker in the current session (AskUserQuestion actually
  shown to Jacob) is the end-to-end test — performed after review passes.
