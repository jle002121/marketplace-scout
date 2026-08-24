# Marketplace Scout Instructions

Use the most recent applicable file under `specs/` as the behavioral source of truth; `specs/marketplace-scout.md` is the baseline. Preserve unrelated user changes.

- Run with `./scout <preset-or-query>` or `python3 scout.py ...`; inspect `./scout --help` before changing CLI behavior.
- `config.json`, `fb_cookies.json`, `seen_listings.db`, generated reports, and browser/session data are private local state. Never print, commit, reset, or replace them unless Jacob explicitly asks.
- Marketplace pages change frequently. Diagnose selectors against current page behavior before changing parsing logic.
- Validate Python syntax and run a narrow representative command that does not erase history or trigger a login flow. Do not use `--reset` without explicit approval.

