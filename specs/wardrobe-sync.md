# Spec: wardrobe sync — `scout clothes` follows the vault note automatically

## Goal

When Jacob adds/removes items in the vault note
`~/Documents/MyVault/20 Areas/Personal/Wardrobe — Timeless Functional Aesthetic.md`,
`./scout clothes` picks up the changes automatically — no manual config.json
editing. The note stays a normal human-readable markdown note (no special
syntax required in it).

## Requirements

### R1 — `sync_wardrobe.py` script in ~/marketplace-scout
A standalone script that parses the wardrobe note and regenerates the clothes
presets in `config.json`:

- Finds every markdown table in the note whose header row contains both a
  `Brand` and a `Model` column. Tables without those columns (e.g. the Budget
  Buying Order table) are ignored automatically.
- Tracks the nearest preceding `##`/`###` heading for each table; skips tables
  whose heading contains (case-insensitive) any substring in the configured
  `skip_sections` list.
- For each row: extract Brand and Model cells, strip markdown bold (`**`),
  parentheticals (`(...)`), and double quotes.
- Split the Model cell on `" or "` and `" / "` into alternatives — each
  alternative becomes its own preset (e.g. "Iron Ranger or Moc Toe" → 2 presets).
- If the Model cell is empty, `—`, or "Any model" (case-insensitive), the query
  is the brand alone.
- Query generation: `search_brand + " " + alternative`, lowercased, whitespace
  collapsed, truncated to at most 4 words. `search_brand` comes from the
  configured `brand_overrides` map when present (e.g. "Red Wing Heritage" →
  "red wing"), else the brand cell lowercased.
- Preset key (slug): lowercase alphanumerics of brand + alternative
  (e.g. `redwingironranger`).
- Apply configured `skip_presets` (list of slugs to drop) and
  `query_overrides` (slug → replacement query, NOT truncated).
- Rewrite `config.json`: remove all presets currently listed in the `clothes`
  group, insert the newly generated ones, and set the `clothes` group's
  `presets` list to the new slugs. Everything else in config.json (surf/paddle
  presets, platforms on the clothes group, other settings) is preserved.
- `--dry-run` flag: print a table of section → slug → query and what would be
  added/removed, without writing config.json.
- Normal run prints a short summary to stderr: N presets synced, plus any
  added/removed slugs versus the previous clothes group.
- If the note file is missing/unreadable: print a warning to stderr and exit 0
  WITHOUT modifying config.json (so scout falls back to existing presets).

### R2 — Sync settings live in config.json
New top-level `"wardrobe_sync"` object in `config.json`:
```json
{
  "note": "/Users/jacoble/Documents/MyVault/20 Areas/Personal/Wardrobe — Timeless Functional Aesthetic.md",
  "skip_sections": ["Socks", "Walking"],
  "brand_overrides": { "Red Wing Heritage": "red wing", ... },
  "skip_presets": [ ... ],
  "query_overrides": { ... }
}
```
Seed `skip_presets` / `query_overrides` / `brand_overrides` so that the synced
result keeps today's curated behavior:
- All 14 current clothes queries still present (exact query strings preserved
  via overrides where auto-generation differs).
- Cheap-new / not-worth-secondhand items skipped: Dickies 874, Darn Tough
  (whole Socks section), Rainbow Sandals, Vans, walking shoes section.
- Long auto-queries that would fight the ALL-keywords relevance filter get
  overrides (e.g. Thorogood → "thorogood moc toe", Outerknown → "outerknown
  shorts").
- Newly picked-up rows that were not in the manual 14 (e.g. Nicks Boots,
  Bailey's, Pointer Brand, Bedrock, Carhartt K87/carpenter/shorts, Portuguese
  Flannel) are allowed to join the group with sensible queries — that is the
  point of the feature.

### R3 — Auto-sync on `scout clothes`
- The `clothes` group object in config.json gains `"sync": "sync_wardrobe.py"`.
- In `scout.py`: after arg parsing and config load, if any requested query
  resolves to a group carrying a `"sync"` key, run that script (same Python
  interpreter, cwd = scout dir) BEFORE expansion, then reload
  config/presets/groups. Print one stderr line noting the sync ran.
- New `--no-sync` flag skips this step.
- If the sync script exits non-zero or crashes: warn on stderr and continue
  with the existing config (a stale preset list must never block a search).
- Groups without a `"sync"` key (surf/paddle/all) are completely unaffected;
  plain-query runs never trigger sync.

### R4 — Round-trip correctness
After running `sync_wardrobe.py` against the current note:
- `./scout --list-presets` shows the synced clothes presets and the clothes
  group still lists 6 clothing platforms.
- The 14 existing curated queries all still appear among the synced presets'
  queries (allowing additional new presets from note rows previously excluded
  by hand).
- Running sync twice in a row is idempotent (second run reports no changes).
- config.json remains valid JSON and surf/paddle/all groups are byte-identical
  in content.

## Verification
- `python3 sync_wardrobe.py --dry-run` output reviewed against the note tables.
- Real sync run, then `--list-presets`, then second sync proves idempotence.
- `./scout clothes` (killed after startup) shows the sync line + parallel
  query count; `./scout clothes --no-sync` shows no sync line.
- `./scout surf` startup shows no sync line.
- Simulate missing note (temp config pointing at nonexistent path): sync warns,
  exits 0, config untouched; `scout clothes` still starts.
