# Spec: "clothes" preset group — one-command wardrobe hunt

## Goal

`./scout clothes` runs every saved wardrobe search from the vault note
`20 Areas/Personal/Wardrobe — Timeless Functional Aesthetic.md` in one shot,
automatically using the clothing platform set (craigslist, offerup, facebook,
mercari, depop, poshmark) without Jacob having to type `--platforms ...`.

## Requirements

### R1 — Clothes presets in config.json
Add these presets to the `"presets"` object in `config.json` (keep all existing
presets untouched). Queries are broad brand+model (no sizes — listing titles are
inconsistent about sizes; Jacob filters by eye):

| Preset key      | Query                                  |
|-----------------|----------------------------------------|
| ironranger      | red wing iron ranger                   |
| moctoe          | red wing moc toe                       |
| thorogood       | thorogood moc toe                      |
| blundstone      | blundstone chelsea boots               |
| jimgreen        | jim green boots                        |
| nb990           | new balance 990 made in usa            |
| carharttpants   | carhartt double front pants            |
| detroitjacket   | carhartt detroit jacket                |
| filsontin       | filson tin cloth                       |
| filsonmackinaw  | filson mackinaw wool                   |
| pendleton       | pendleton board shirt                  |
| barbour         | barbour bedale wax jacket              |
| birdwell        | birdwell beach britches                |
| vintagebr       | vintage banana republic safari shirt   |

### R2 — "clothes" group with per-group platforms
Add a `"clothes"` group to `"groups"` in `config.json` containing all 14 preset
keys from R1. The group must carry the clothing platform list so it runs on:
`craigslist, offerup, facebook, mercari, depop, poshmark`.

### R3 — Per-group platform override in scout.py
Extend group handling in `scout.py` so a group value may be EITHER:
- a plain list of preset names (existing format — must keep working unchanged), OR
- an object: `{"presets": [...], "platforms": [...]}`

When a group with `"platforms"` is expanded and the user did NOT pass
`--platforms` on the command line, that group's platforms are used for the run.
An explicit `--platforms` flag always wins over the group's platforms.

### R4 — --list-presets handles both group forms
`./scout --list-presets` must not crash and must print the member preset names
for both list-form and object-form groups (for object-form, also show its
platforms).

### R5 — Existing behavior unchanged
- `./scout surf`, `./scout paddle`, `./scout all` still work exactly as before
  (list-form groups, default platforms from config).
- Direct queries (`./scout "red wing iron ranger"`) unchanged.
- `config.example.json` gets one small object-form group example so the format
  is documented.

## Verification
- `./scout --list-presets` shows all 14 clothes presets and the clothes group
  with its platforms, plus the old surf/paddle/all groups.
- `python3 -c` (or equivalent) sanity check: expanding `clothes` yields 14
  queries and sets platforms to the 6 clothing platforms; expanding `surf`
  leaves platforms at the config default.
- No full scrape run required (takes many minutes) — logic-level verification
  is sufficient, but the command must at least start a real run without
  erroring on argument/config parsing.
