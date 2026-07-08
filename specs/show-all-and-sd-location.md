# Spec: Show all quality-passed listings + lock location to San Diego

Changes to `~/marketplace-scout/scout.py` and `config.json`. Persistent defaults —
no new flags required for normal use.

## R1 — Show everything that passes the quality filter

- Change `--limit` default from `15` to `0` (0 = show all). Update help text to
  say `(default: 0 = show all)`.
- The report must contain **every** listing that passes the quality filter,
  ranked by price ascending, when no `--limit` is given.
- `--limit N` still works as an explicit cap for users who want one.

## R2 — Stop de-emphasizing previously-seen listings

- Remove the `opacity:0.6` dimming applied to non-new cards in `card_html`.
  All cards render at full opacity.
- Keep the green "New" badge as an informational marker only.
- Update the stdout summary line so the shown count is explicit, e.g.:
  `Found 429 listings · 125 passed quality filter · 125 shown (11 new) · Report: …`

## R3 — Craigslist restricted to San Diego area

- Add config keys `craigslist_postal` (default `"92123"`) and
  `craigslist_search_distance` (default `40`, miles) to `DEFAULT_CONFIG` and
  `config.json`.
- Craigslist search URL must include `&postal=<postal>&search_distance=<distance>`
  so results are confined to a radius around central San Diego, which prevents
  Craigslist's "nearby areas" spillover (Westminster, San Pedro, Moreno Valley…).

## R4 — Facebook Marketplace scoped to San Diego

- Add config key `facebook_city` (default `"sandiego"`) to `DEFAULT_CONFIG` and
  `config.json`.
- Facebook search must use the city-scoped path:
  `https://www.facebook.com/marketplace/{facebook_city}/search?query=...`
  instead of the account-location path `/marketplace/search`.

## R5 — OfferUp biased to San Diego

- Create the Playwright browser context with San Diego geolocation
  (`latitude 32.7157, longitude -117.1611`) and `geolocation` permission
  granted, so OfferUp's location detection resolves to San Diego rather than
  IP/account guess. (OfferUp has no reliable URL location param; geolocation is
  the best-effort mechanism. Mercari/Depop/Poshmark are shipping platforms —
  location does not apply.)

## R6 — Config persistence

- `config.json` on disk updated with the new keys so the behavior sticks for
  all future runs. `DEFAULT_CONFIG` in scout.py kept in sync.

## R7 — Verification

- Run `./scout "dutch oven"` (or similar) after the change and confirm:
  - shown count == quality-passed count in the summary line,
  - Craigslist result URLs/titles no longer come from LA/OC cities
    (spot-check a few listing locations),
  - the run completes without errors on all three default platforms.

## R8 — Commit

- Commit the changes in the `~/marketplace-scout` git repo with a descriptive
  message.
