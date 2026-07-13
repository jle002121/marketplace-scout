# Spec: "bikes" preset group — retro-mod rigid MTB beaters

## Goal

`./scout bikes` hunts the early-90s rigid mountain bikes Jacob loves from
retro-mod Instagram reels (Trek 6000-class, Specialized Hardrock/Rockhopper,
GT, Bridgestone) — fun, cool, easy to fix, easy to ride. No price cap.
Local-pickup item → default 3 platforms (craigslist, offerup, facebook);
the group must NOT force the clothing platforms.

## Requirements

### R1 — Bike presets in config.json
Add to `"presets"` (existing presets untouched):

| Key | Query |
|---|---|
| vintagetrek     | vintage trek |
| hardrock        | specialized hardrock |
| rockhopper      | specialized rockhopper |
| stumpjumper     | specialized stumpjumper |
| gtmtb           | gt mountain bike |
| bridgestonemtb  | bridgestone mountain bike |
| vintagemtb      | vintage mountain bike |

### R2 — "bikes" group
Add `"bikes"` group to `"groups"` as a **plain list** of the 7 preset keys
(list form → default platforms, which is correct for bikes). The
wardrobe-synced `clothes` group and surf/paddle/all are untouched — and the
wardrobe sync must not remove the bike presets (they are not in the clothes
group, so `sync_wardrobe.py` leaves them alone; verify this).

### R3 — Docs & memory
- Vault `10 Projects/Marketplace Scout.md`: add the bikes presets + group to
  the preset/group tables.
- Vault `10 Projects/Tacoma Camping Setup — Bike Rack & Bikes.md`: one line
  noting `scout bikes` now exists for the around-camp beater hunt.
- Memory `user_interests.md` bikes section: `./scout bikes` = saved retro-MTB
  hunt; "run bikes" from Jacob means this group now (NOT the vintage-Schwinn
  ad-hoc queries used July 9, 2026).

## Verification
- `./scout --list-presets` shows the 7 presets and the bikes group without
  platform suffix.
- `./scout bikes` starts, expands to 7 queries, shows NO sync line and NO
  clothing platforms (check stderr/header).
- Run `sync_wardrobe.py` once after adding: bike presets survive, clothes
  group unchanged.
- Docs/memory greps confirm R3.
