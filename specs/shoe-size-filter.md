# Spec: shoe size filter — footwear listings must match Jacob's sizes

## Goal

Shoe/boot/sneaker listings whose title declares a size outside Jacob's range
must not appear in reports. Sizes come from the second brain (vault note
`20 Areas/Personal/Wardrobe — Timeless Functional Aesthetic.md`): Iron
Ranger 10, Moc Toe 10.5, Vans lace-up 10.5 / Slip-On 11 → allowed window
**10, 10.5, 11**. Observed noise this filter must kill (real titles from the
July 9, 2026 run): "New Balance 993 Grey White Sneakers Womens U.S. 6",
"...Size 15", "...Running Shoes Womens Size 7".

## Requirements

### R1 — `my_shoe_sizes` config key
- `config.json`: `"my_shoe_sizes": ["10", "10.5", "11"]`.
- `config.example.json`: same key (any example values) so it's documented.
- Absent or empty list → filter fully disabled (backward compatible).

### R2 — Size filter in scout.py
A new function applied to listings right after the existing quality filter:

1. **Declared-size rule:** extract numeric size declarations from the title
   with patterns covering at least: `size 9`, `Size 9.5`, `sz 9`, `sz. 9`,
   `US 9`, `U.S. 9`, `men's 9` / `mens 9`. If a declared value is ≤ 16 (shoe
   range — waist sizes like 32/34 are all > 16 and must NOT trigger this
   rule) and no declared shoe-range value matches an allowed size
   (numeric comparison: "10.5" matches 10.5), drop the listing.
2. **Women's/kids rule:** drop the listing if the title contains a
   women's/kids marker (`womens`, `women's`, `wmns`, `girls`, `kids`,
   `youth`, `toddler`) AND the title also contains either a footwear word
   (`boot`, `shoe`, `sneaker`, `sandal`, `chelsea`, `oxford`, `running`,
   `runner`, `trainer`) or a declared shoe-range size. Non-footwear
   women's items (e.g. a women's flannel) are out of scope and kept.
3. **No declaration → keep:** titles with no size information pass through
   (seller didn't list a size; Jacob can ask).
4. Report the number of size-filtered listings in the existing stderr/summary
   flow (a simple count line is fine).

### R3 — Real-title behavior (must hold exactly)
| Title | Outcome |
|---|---|
| "New Balance 993 Grey White Sneakers Womens U.S. 6" | dropped |
| "THRASHED ! New Balance 993 Heritage USA Grey Suede Mesh Running Shoes Size 15" | dropped |
| "New Balance 993 Black WR993BK Running Shoes Womens Size 7" | dropped |
| "New Balance 990v5 Navy M990NV5 Men's Size 11 Made in USA" | kept |
| "Red Wing Iron Ranger sz 10.5" | kept |
| "Red Wing Iron Ranger size 9D" | dropped |
| "New Balance 990 V4 Made In USA" | kept (no size declared) |
| "1990s Pointer Brand pants" | kept (not footwear, no shoe size) |
| "Carhartt double front pants size 32" | kept (32 > 16 — waist, not shoe) |
| "Pendleton womens flannel" | kept (women's but not footwear) |

### R4 — Docs & memory
- Vault doc `10 Projects/Marketplace Scout.md`: short section on the size
  filter — what it drops, that unsized listings still show, where to change
  sizes (`my_shoe_sizes` in config.json), sizes sourced from the wardrobe
  note.
- Memory `feedback_marketplace_clothes.md`: one line noting scout now
  auto-filters shoe sizes to 10–11 and that NB size is unconfirmed (window
  assumed from Vans/Red Wing sizes).

## Verification
- Unit-style check runs every R3 title through the filter and asserts the
  exact outcomes.
- `./scout --list-presets` still exits 0 (config valid).
- Real re-run of the two New Balance presets shows fewer shown listings than
  this morning's 147-report equivalents and zero titles declaring sizes
  outside 10–11.
