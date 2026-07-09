#!/usr/bin/env python3
"""Regenerate the 'clothes' presets in config.json from the wardrobe vault note.

Parses every markdown table with Brand + Model columns in the note configured
at config.json → wardrobe_sync.note, turns each row into search presets, and
rewrites the 'clothes' group. Settings (skip_sections, skip_presets,
brand_overrides, query_overrides) live under "wardrobe_sync" in config.json.

Usage:  python3 sync_wardrobe.py [--dry-run]
"""
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CFG_PATH = BASE_DIR / "config.json"

CLOTHES_PLATFORMS = ["craigslist", "offerup", "facebook", "mercari", "depop", "poshmark"]


def clean(text):
    """Strip markdown bold, parentheticals, and double quotes; collapse spaces."""
    text = text.replace("**", "")
    text = re.sub(r"\([^)]*\)", "", text)
    text = text.replace('"', "")
    return re.sub(r"\s+", " ", text).strip()


def slugify(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def parse_note(md, skip_sections):
    """Yield (section, brand, model) for every row of every Brand/Model table."""
    rows = []
    heading = ""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^#{2,3}\s+(.*)", lines[i])
        if m:
            heading = m.group(1).strip()
            i += 1
            continue
        if lines[i].lstrip().startswith("|"):
            header = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if "Brand" in header and "Model" in header:
                bi, mi = header.index("Brand"), header.index("Model")
                skip = any(s.lower() in heading.lower() for s in skip_sections)
                i += 2  # skip header + separator row
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not skip and len(cells) > max(bi, mi):
                        brand, model = clean(cells[bi]), clean(cells[mi])
                        if brand:
                            rows.append((heading, brand, model))
                    i += 1
                continue
        i += 1
    return rows


def generate(rows, settings):
    """Turn note rows into {slug: query}. Returns (presets, report_lines)."""
    brand_overrides = settings.get("brand_overrides", {})
    skip_presets = set(settings.get("skip_presets", []))
    query_overrides = settings.get("query_overrides", {})
    presets = {}
    report = []
    for section, brand, model in rows:
        search_brand = brand_overrides.get(brand, brand.lower())
        if not model or model.lower() in ("any model", "any", "—", "-"):
            alts = [""]
        else:
            alts = [a.strip() for a in re.split(r"\s+or\s+|\s+/\s+", model) if a.strip()]
        for alt in alts:
            slug = slugify(brand + alt)
            if slug in skip_presets:
                report.append((section, slug, "(skipped)"))
                continue
            if slug in query_overrides:
                query = query_overrides[slug]
            else:
                query = " ".join(f"{search_brand} {alt}".lower().split()[:4])
            presets[slug] = query
            report.append((section, slug, f'"{query}"'))
    return presets, report


def main():
    dry_run = "--dry-run" in sys.argv

    config = json.loads(CFG_PATH.read_text())
    settings = config.get("wardrobe_sync")
    if not settings or not settings.get("note"):
        print("  Warning: no wardrobe_sync settings in config.json — nothing to sync.", file=sys.stderr)
        return
    note_path = Path(settings["note"])
    try:
        md = note_path.read_text()
    except OSError as e:
        print(f"  Warning: wardrobe note unreadable ({e}) — keeping existing presets.", file=sys.stderr)
        return

    rows = parse_note(md, settings.get("skip_sections", []))
    new_presets, report = generate(rows, settings)

    groups = config.setdefault("groups", {})
    group = groups.get("clothes")
    if not isinstance(group, dict):
        group = {"presets": group or [], "platforms": CLOTHES_PLATFORMS, "sync": "sync_wardrobe.py"}
        groups["clothes"] = group
    old_slugs = list(group.get("presets", []))

    added = [s for s in new_presets if s not in old_slugs]
    removed = [s for s in old_slugs if s not in new_presets]

    if dry_run:
        print(f"\nWardrobe note: {note_path}")
        width = max((len(s) for _, s, _ in report), default=0)
        for section, slug, query in report:
            print(f"  {section:<28} {slug:<{width}} → {query}")
        print(f"\nWould keep {len(new_presets)} presets"
              f" (+{len(added)} added, -{len(removed)} removed vs current clothes group)")
        return

    presets = config.setdefault("presets", {})
    for slug in old_slugs:
        presets.pop(slug, None)
    presets.update(new_presets)
    group["presets"] = list(new_presets)
    CFG_PATH.write_text(json.dumps(config, indent=2) + "\n")

    if added or removed:
        detail = ", ".join(f"+{s}" for s in added) + (", " if added and removed else "") \
                 + ", ".join(f"-{s}" for s in removed)
        print(f"  Synced {len(new_presets)} clothes presets from wardrobe note ({detail})", file=sys.stderr)
    else:
        print(f"  Synced {len(new_presets)} clothes presets from wardrobe note (no changes)", file=sys.stderr)


if __name__ == "__main__":
    main()
