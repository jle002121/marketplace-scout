# Spec: concurrency cap — big multi-query runs must not time themselves out

## Problem

`scrape_all_async` launches one task per query and every task opens all
platform pages simultaneously. A `scout clothes` run (27 queries × 6
platforms = 162 concurrent pages) saturates the machine/network: OfferUp,
Mercari, and Poshmark all hit their 30 s `Page.goto` timeouts (observed:
81/81 pages timed out on a 27×3 run, while a 1×3 run of the same code
returned 123 listings instantly). Runs up to ~27 concurrent pages (surf:
9×3) have always worked.

## Requirements

### R1 — Semaphore on per-query tasks in scout.py
In `scrape_all_async`, gate `_scrape_query_async` behind an
`asyncio.Semaphore` so that at most `max_parallel_queries` queries are
in flight at once (each query still scrapes its platforms in parallel
internally — the cap is on concurrent queries, giving
`max_parallel_queries × len(platforms)` max concurrent pages).

- Cap value comes from `config["max_parallel_queries"]`, defaulting to 4
  when the key is absent or invalid (≤ 0 / non-int).
- Results, ordering semantics, and error handling
  (`return_exceptions=True`) unchanged.
- Progress: print one short stderr line per completed query
  (`  [n/total] done: "<query>"`) so long runs aren't silent.

### R2 — Config
- `config.json`: add `"max_parallel_queries": 4`.
- `config.example.json`: same key with the same default so the format is
  documented.

### R3 — Small runs unaffected
Runs with ≤ `max_parallel_queries` queries behave exactly as before
(single query, surf group) — the semaphore never blocks them.

## Verification
- Logic check: with `max_parallel_queries = 2` and instrumented fake
  scrapers, observed peak concurrency is exactly 2 for 6 queries and
  results for all 6 come back.
- Real run: `./scout clothes --no-sync --platforms offerup mercari poshmark`
  completes with OU/MC/PM listings actually returned (this exact
  invocation returned 0 listings / 78 timeouts before the fix).
