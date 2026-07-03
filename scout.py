#!/usr/bin/env python3
"""
Marketplace Scout v2
On-demand search across Craigslist, OfferUp, and Facebook Marketplace.
Generates a photo-rich HTML report and auto-opens it in your browser.

Usage:
  python3 scout.py "electric drum kit"
  python3 scout.py "electric drum kit" --max-price 500
  python3 scout.py --login-facebook
  python3 scout.py --reset
"""

import argparse
import asyncio
import html as html_mod
import json
import math
import re
import sqlite3
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR  = Path(__file__).parent
DB_PATH   = BASE_DIR / "seen_listings.db"
CFG_PATH  = BASE_DIR / "config.json"
COOK_PATH = BASE_DIR / "fb_cookies.json"
HTML_PATH = BASE_DIR / "report.html"

DEFAULT_CONFIG = {
    "location": "San Diego, CA",
    "craigslist_subdomain": "sandiego",
    "platforms": ["craigslist", "offerup", "facebook"],
}

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# ── Database ───────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id         TEXT PRIMARY KEY,
            platform   TEXT,
            title      TEXT,
            price      TEXT,
            url        TEXT,
            first_seen TEXT
        )
    """)
    conn.commit()
    return conn


def is_new(conn, lid):
    return conn.execute("SELECT 1 FROM listings WHERE id=?", (lid,)).fetchone() is None


def save_listing(conn, listing):
    conn.execute(
        "INSERT OR IGNORE INTO listings (id, platform, title, price, url, first_seen) "
        "VALUES (?,?,?,?,?,?)",
        (listing["id"], listing["platform"], listing["title"],
         listing["price"], listing["url"], datetime.now().isoformat())
    )
    conn.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_price(text):
    """Extract a numeric float from price text like '$250', '$1,200', '250'."""
    cleaned = re.sub(r'[^\d.]', '', text.replace(',', ''))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def make_id(platform, url):
    """Stable listing ID derived from platform + URL ID."""
    patterns = {
        "craigslist": r'/(\d+)\.html',
        "offerup":    r'/item/(?:detail/)?([a-zA-Z0-9-]+?)(?:/|$)',
        "facebook":   r'/marketplace/item/(\d+)',
    }
    m = re.search(patterns.get(platform, r'(\w+)$'), url)
    return f"{platform[:2]}_{m.group(1)}" if m else f"{platform[:2]}_{abs(hash(url))}"


# ── Scrapers ───────────────────────────────────────────────────────────────────

async def scrape_craigslist(query, config, context):
    """Async Playwright scrape of Craigslist search results page."""
    listings = []
    subdomain = config.get("craigslist_subdomain", "sandiego")
    q = query.replace(" ", "+")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://{subdomain}.craigslist.org/search/sss?query={q}",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(2000)

        # Expand viewport to a very large height so every card is "in viewport".
        # Native loading="lazy" uses the Intersection Observer against viewport bounds —
        # a tall viewport means all images are visible at once and the browser fetches
        # every one immediately, no scrolling needed.
        await page.set_viewport_size({"width": 1280, "height": 16000})
        await page.wait_for_timeout(500)

        # Also cover old-style JS data-src lazy loaders (some CL listing types use these)
        await page.evaluate("""
            document.querySelectorAll('img[data-src], img[data-lazy]').forEach(img => {
                const ds = img.getAttribute('data-src') || img.getAttribute('data-lazy');
                if (ds) img.src = ds;
            });
        """)

        # Wait for image requests to settle
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            await page.wait_for_timeout(3000)

        rows = await page.eval_on_selector_all(
            ".cl-search-result",
            """cards => cards.map(el => {
                const linkEl  = el.querySelector('a.main');
                const imgEl   = el.querySelector('img');
                const priceEl = el.querySelector('.priceinfo');
                const metaEl  = el.querySelector('.meta');
                // data-src first (old lazy loaders); fall through to src (native lazy)
                const imgSrc  = imgEl
                    ? (imgEl.getAttribute('data-src') || imgEl.getAttribute('data-lazy') || imgEl.src || '')
                    : '';
                return {
                    pid:   el.getAttribute('data-pid') || '',
                    title: el.getAttribute('title') || '',
                    url:   linkEl  ? linkEl.href              : '',
                    img:   imgSrc,
                    price: priceEl ? priceEl.innerText.trim() : '',
                    meta:  metaEl  ? metaEl.innerText.trim()  : '',
                };
            })"""
        )

        for r in rows:
            if not r.get("url") or not r.get("pid"):
                continue
            title   = r.get("title", "")
            desc    = (title + " " + r.get("meta", "")).strip()
            img_url = r.get("img", "")
            lid     = f"cl_{r['pid']}"
            listings.append({
                "id":            lid,
                "platform":      "craigslist",
                "title":         title,
                "price":         r.get("price", ""),
                "price_numeric": parse_price(r.get("price", "")),
                "url":           r["url"],
                "img":           img_url,
                "has_photo":     bool(img_url and img_url.startswith("http")),
                "desc_length":   len(desc),
            })
    except Exception as e:
        print(f"  [CL:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


async def scrape_offerup(query, config, context):
    """Async Playwright scrape of OfferUp search results."""
    listings = []
    q = query.replace(" ", "+")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://offerup.com/search/?q={q}",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(3500)

        items = await page.eval_on_selector_all(
            'a[href*="/item/"]',
            """els => els.map(e => ({
                href: e.href,
                text: e.innerText.trim(),
                img:  e.querySelector('img') ? e.querySelector('img').src : '',
            }))"""
        )

        seen = set()
        for el in items:
            href = el.get("href", "")
            text = el.get("text", "")
            img  = el.get("img", "")

            m = re.search(r'/item/(?:detail/)?([a-zA-Z0-9-]+?)(?:/|$)', href)
            if not m:
                continue
            lid = f"ou_{m.group(1)}"
            if lid in seen:
                continue
            seen.add(lid)

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            price = next((l for l in lines if l.startswith("$")), "")
            title = next((l for l in lines if not l.startswith("$") and len(l) > 2), "")

            listings.append({
                "id":            lid,
                "platform":      "offerup",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           href,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(text),
            })
    except Exception as e:
        print(f"  [OU:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


async def scrape_facebook(query, config, context):
    """Async Playwright scrape of Facebook Marketplace (requires saved cookies).
    Returns (listings, skip_reason) where skip_reason is None on success or a string if FB was skipped.
    """
    listings = []

    if not COOK_PATH.exists():
        msg = "no cookies — run: scout --login-facebook"
        print(f"  [FB] No cookies found — skipping. Run with --login-facebook first.", file=sys.stderr)
        return listings, msg

    page = await context.new_page()
    try:
        await context.add_cookies(json.loads(COOK_PATH.read_text()))
        q = query.replace(" ", "%20")
        await page.goto(
            f"https://www.facebook.com/marketplace/search?query={q}",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(4000)

        # FB redirects to login/checkpoint/home when session is dead
        bad_url = ("login" in page.url or "checkpoint" in page.url
                   or "marketplace" not in page.url)
        if bad_url:
            msg = "session expired — run: scout --login-facebook"
            print(f"  [FB] Session expired (landed on {page.url}) — run with --login-facebook to re-auth.", file=sys.stderr)
            return listings, msg

        items = await page.eval_on_selector_all(
            'a[href*="/marketplace/item/"]',
            """els => els.map(e => ({
                href: e.href,
                text: e.innerText.trim(),
                img:  e.querySelector('img') ? e.querySelector('img').src : '',
            }))"""
        )

        seen = set()
        for el in items:
            href = el.get("href", "").split("?")[0]
            text = el.get("text", "")
            img  = el.get("img", "")

            m = re.search(r'/marketplace/item/(\d+)', href)
            if not m:
                continue
            lid = f"fb_{m.group(1)}"
            if lid in seen:
                continue
            seen.add(lid)

            if not href.startswith("http"):
                href = "https://www.facebook.com" + href

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            price = next((l for l in lines if l.startswith("$")), "")
            title = next((l for l in lines if not l.startswith("$") and len(l) > 2), "")

            listings.append({
                "id":            lid,
                "platform":      "facebook",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           href,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(text),
            })
    except Exception as e:
        print(f"  [FB:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings, None


# ── Additional platform scrapers ──────────────────────────────────────────────

async def scrape_ebay(query, config, context):
    """Async scrape of eBay used-item listings."""
    listings = []
    q = query.replace(" ", "+")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://www.ebay.com/sch/i.html?_nkw={q}&LH_ItemCondition=3000&_ipg=60&LH_PrefLoc=1",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(2500)

        items = await page.eval_on_selector_all(
            '.s-item:not(.s-item--watch-at-corner)',
            """els => els.map(e => ({
                title: (e.querySelector('.s-item__title span') || e.querySelector('.s-item__title'))?.innerText?.trim() || '',
                price: e.querySelector('.s-item__price')?.innerText?.trim() || '',
                url:   e.querySelector('a.s-item__link')?.href || '',
                img:   e.querySelector('.s-item__image-wrapper img')?.src || e.querySelector('.s-item__image img')?.src || '',
            }))"""
        )

        for el in items:
            url = el.get("url", "")
            title = el.get("title", "")
            if not url or title.lower() == "shop on ebay":
                continue
            m = re.search(r'/itm/(?:[^/]+/)?(\d+)', url)
            lid = f"eb_{m.group(1)}" if m else f"eb_{abs(hash(url))}"
            price = el.get("price", "").split(" to ")[0]  # take lower of price range
            img = el.get("img", "")
            listings.append({
                "id":            lid,
                "platform":      "ebay",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           url,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(title),
            })
    except Exception as e:
        print(f"  [EB:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


async def scrape_mercari(query, config, context):
    """Async scrape of Mercari listings."""
    listings = []
    q = query.replace(" ", "%20")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://www.mercari.com/search/?keyword={q}",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(4000)

        items = await page.eval_on_selector_all(
            'a[href*="/item/"]',
            """els => els.map(e => ({
                href:  e.href,
                text:  e.innerText.trim(),
                img:   e.querySelector('img')?.src || '',
            }))"""
        )

        seen = set()
        for el in items:
            href = el.get("href", "")
            text = el.get("text", "")
            img  = el.get("img", "")
            m = re.search(r'/item/(m\d+)', href)
            if not m:
                continue
            lid = f"mc_{m.group(1)}"
            if lid in seen:
                continue
            seen.add(lid)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            price = next((l for l in lines if l.startswith("$")), "")
            title = next((l for l in lines if not l.startswith("$") and len(l) > 2), "")
            listings.append({
                "id":            lid,
                "platform":      "mercari",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           href,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(text),
            })
    except Exception as e:
        print(f"  [MC:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


async def scrape_depop(query, config, context):
    """Async scrape of Depop listings. Titles are JS-loaded so we derive them from the URL slug."""
    listings = []
    q = query.replace(" ", "%20")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://www.depop.com/search/?q={q}",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(5000)

        items = await page.eval_on_selector_all(
            'a[href*="/products/"]',
            """els => els.map(e => ({
                href:  e.href,
                img:   e.querySelector('img')?.src || '',
                alt:   e.querySelector('img')?.alt || '',
                price: e.querySelector('[class*="price"]')?.innerText?.trim() || '',
            }))"""
        )

        seen = set()
        for el in items:
            href = el.get("href", "")
            img  = el.get("img", "")
            alt  = el.get("alt", "")
            price = el.get("price", "")
            m = re.search(r'/products/([^/?]+)', href)
            if not m:
                continue
            lid = f"dp_{m.group(1)}"
            if lid in seen:
                continue
            seen.add(lid)
            if not href.startswith("http"):
                href = "https://www.depop.com" + href
            # Derive title from URL slug (e.g. "vintage-90s-levis-jeans" → "vintage 90s levis jeans")
            slug = m.group(1)
            slug_parts = re.sub(r'^[a-z0-9]+-', '', slug)  # strip seller prefix
            title = alt or slug_parts.replace("-", " ").title()
            listings.append({
                "id":            lid,
                "platform":      "depop",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           href,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(title) + len(price),
            })
    except Exception as e:
        print(f"  [DP:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


async def scrape_poshmark(query, config, context):
    """Async scrape of Poshmark listings.
    Each card has two <a> tags with the same href — one has the image, one has the text.
    We group by listing ID and merge both.
    """
    listings = []
    q = query.replace(" ", "%20")
    page = await context.new_page()
    try:
        await page.goto(
            f"https://poshmark.com/search?query={q}&type=listings&src=dir",
            wait_until="domcontentloaded", timeout=30000
        )
        await page.wait_for_timeout(3500)

        items = await page.eval_on_selector_all(
            'a[href*="/listing/"]',
            """els => els.map(e => ({
                href:  e.href,
                text:  e.innerText.trim(),
                img:   e.querySelector('img')?.src || '',
            }))"""
        )

        # Group by listing ID — merge text and img from duplicate links
        merged = {}
        for el in items:
            href = el.get("href", "")
            m = re.search(r'/listing/([^/?]+)', href)
            if not m:
                continue
            lid = f"pm_{m.group(1)}"
            if lid not in merged:
                merged[lid] = {"href": href, "text": "", "img": ""}
            if el.get("text"):
                merged[lid]["text"] = el["text"]
            if el.get("img"):
                merged[lid]["img"] = el["img"]

        for lid, el in merged.items():
            href = el["href"]
            text = el["text"]
            img  = el["img"]
            if not href.startswith("http"):
                href = "https://poshmark.com" + href
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            price = next((l for l in lines if l.startswith("$")), "")
            title = next((l for l in lines if not l.startswith("$") and len(l) > 2), "")
            listings.append({
                "id":            lid,
                "platform":      "poshmark",
                "title":         title,
                "price":         price,
                "price_numeric": parse_price(price),
                "url":           href,
                "img":           img,
                "has_photo":     bool(img and img.startswith("http")),
                "desc_length":   len(text),
            })
    except Exception as e:
        print(f"  [PM:{query}] Error: {e}", file=sys.stderr)
    finally:
        await page.close()
    return listings


# ── Async parallel scraper ────────────────────────────────────────────────────

async def _scrape_query_async(query, config, browser):
    """Scrape all platforms for one query; each query gets its own context.
    Returns (listings, fb_skip_reason).
    """
    from playwright.async_api import async_playwright  # noqa — imported for type only
    context = await browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900})
    listings = []
    fb_skip = None
    platforms = config.get("platforms", ["craigslist", "offerup", "facebook"])
    try:
        non_fb_tasks = []
        fb_task = None
        if "craigslist" in platforms:
            non_fb_tasks.append(scrape_craigslist(query, config, context))
        if "offerup" in platforms:
            non_fb_tasks.append(scrape_offerup(query, config, context))
        if "facebook" in platforms:
            fb_task = scrape_facebook(query, config, context)
        # ebay: blocks headless browsers — not supported
        if "mercari" in platforms:
            non_fb_tasks.append(scrape_mercari(query, config, context))
        if "depop" in platforms:
            non_fb_tasks.append(scrape_depop(query, config, context))
        if "poshmark" in platforms:
            non_fb_tasks.append(scrape_poshmark(query, config, context))

        all_tasks = non_fb_tasks + ([fb_task] if fb_task else [])
        results = await asyncio.gather(*all_tasks, return_exceptions=True)

        for i, r in enumerate(results):
            if i < len(non_fb_tasks):
                if isinstance(r, list):
                    listings.extend(r)
            else:
                # FB result is a (listings, skip_reason) tuple
                if isinstance(r, tuple):
                    fb_listings, fb_skip = r
                    listings.extend(fb_listings)
    finally:
        await context.close()
    return listings, fb_skip


async def scrape_all_async(queries, config):
    """Launch one async task per query and gather all results in parallel.
    Returns (all_listings, fb_skip_reason).
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        try:
            tasks = [_scrape_query_async(q, config, browser) for q in queries]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await browser.close()

    all_listings = []
    fb_skip_reason = None
    for r in results:
        if isinstance(r, tuple):
            listings, fb_skip = r
            all_listings.extend(listings)
            if fb_skip:
                fb_skip_reason = fb_skip
    return all_listings, fb_skip_reason


# ── Facebook Login Flow ────────────────────────────────────────────────────────

def do_facebook_login(pw):
    """Open a headed browser, let user log in, save cookies."""
    browser = pw.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 900})
    page    = context.new_page()
    print("\n  Opening browser — log into Facebook, then press Enter here.")
    page.goto("https://www.facebook.com/login", wait_until="networkidle", timeout=30000)
    input("  >> Press Enter once you're fully logged in... ")
    COOK_PATH.write_text(json.dumps(context.cookies()))
    print(f"  Cookies saved → {COOK_PATH}\n")
    browser.close()


# ── Quality Filter ─────────────────────────────────────────────────────────────

_STOP_WORDS = {"a", "an", "the", "for", "in", "at", "by", "to", "of", "and", "or", "with"}


def _word_match(query_word, title_word):
    """True if words match exactly, one is a prefix of the other, or share a 5-char prefix.

    Handles: drum/drums, kit/kits (prefix containment)
             electric/electronic, electric/electrical (5-char prefix: 'elect')
    """
    if query_word == title_word:
        return True
    # One word is a prefix of the other (drum→drums, kit→kits)
    if title_word.startswith(query_word) or query_word.startswith(title_word):
        return True
    # Share a 5-char prefix for longer words (electric↔electronic)
    if min(len(query_word), len(title_word)) >= 5:
        return query_word[:5] == title_word[:5]
    return False


def is_relevant(title, query):
    """Return True if the listing title matches enough query keywords.

    For 1-2 meaningful words: at least 1 must match.
    For 3+ meaningful words: ALL must match (prevents partial-overlap false positives).
    Matching is word-level with 5-char prefix fuzzy match (electric ↔ electronic, drum ↔ drums).
    """
    title_words = set(re.findall(r'\b\w+\b', title.lower()))
    words = [w for w in re.findall(r'\b\w+\b', query.lower())
             if len(w) >= 3 and w not in _STOP_WORDS]
    if not words:
        return True
    # Spec: 1-2 meaningful words → at least 1 must match; 3+ → ALL must match
    threshold = 1 if len(words) <= 2 else len(words)
    matched = sum(
        1 for qw in words
        if any(_word_match(qw, tw) for tw in title_words)
    )
    return matched >= threshold


def quality_filter(listings, query="", min_price=None, max_price=None):
    """Keep listings with photo, substantive description, parseable price, relevance, and within budget."""
    passed = []
    for l in listings:
        if not l.get("has_photo"):
            continue
        if l["desc_length"] < 30:
            continue
        if l["price_numeric"] <= 0:
            continue
        if query and not is_relevant(l["title"], query):
            continue
        if min_price is not None and l["price_numeric"] < min_price:
            continue
        if max_price is not None and l["price_numeric"] > max_price:
            continue
        passed.append(l)
    return passed


# ── Ranking ────────────────────────────────────────────────────────────────────

def rank(listings, top_n=15):
    """Sort by price ascending, flag deals (20%+ below median). top_n defaults to 15 per spec."""
    if not listings:
        return []
    prices = [l["price_numeric"] for l in listings]
    med    = statistics.median(prices)
    for l in listings:
        l["is_deal"] = l["price_numeric"] < med * 0.80
    listings.sort(key=lambda l: l["price_numeric"])
    return listings if top_n is None else listings[:top_n]


# ── HTML Generation ────────────────────────────────────────────────────────────

PLATFORM_LABELS = {"craigslist": "CL", "offerup": "OU", "facebook": "FB",
                   "ebay": "EB", "mercari": "MC", "depop": "DP", "poshmark": "PM"}
PLATFORM_COLORS = {"craigslist": "#6b7280", "offerup": "#f97316", "facebook": "#3b82f6",
                   "ebay": "#e53935", "mercari": "#00b4d8", "depop": "#ff2d55", "poshmark": "#7c3aed"}

CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f3f4f6;
    color: #111827;
    min-height: 100vh;
}
header {
    background: #1f2937;
    color: #fff;
    padding: 24px 32px;
}
header h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: 6px; }
header p  { font-size: 0.9rem; color: #9ca3af; }
.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    padding: 24px 32px;
    max-width: 1200px;
    margin: 0 auto;
}
@media (max-width: 700px)  { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 440px)  { .grid { grid-template-columns: 1fr; } }
.card {
    display: flex;
    flex-direction: column;
    background: #fff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    text-decoration: none;
    color: inherit;
    transition: transform .15s, box-shadow .15s;
}
.card:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,.12); }
.photo {
    width: 100%;
    aspect-ratio: 4/3;
    background: #e5e7eb;
    overflow: hidden;
    flex-shrink: 0;
}
.photo img { width: 100%; height: 100%; object-fit: cover; }
.photo.placeholder {
    display: flex; align-items: center; justify-content: center;
    font-size: 2.5rem; color: #9ca3af;
}
.body { padding: 14px 16px 18px; display: flex; flex-direction: column; gap: 8px; }
.badges { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.badge {
    font-size: 0.68rem; font-weight: 700;
    padding: 2px 8px; border-radius: 20px;
    letter-spacing: .04em; text-transform: uppercase;
    color: #fff;
}
.badge.new-badge { background: #22c55e; }
.badge.deal      { background: #ef4444; }
.price { font-size: 1.4rem; font-weight: 800; color: #111827; }
.title {
    font-size: 0.88rem; color: #4b5563;
    display: -webkit-box; -webkit-line-clamp: 2;
    -webkit-box-orient: vertical; overflow: hidden;
    line-height: 1.45;
}
footer {
    text-align: center; padding: 24px;
    font-size: 0.8rem; color: #9ca3af;
}
.empty {
    grid-column: 1 / -1; text-align: center;
    padding: 60px 20px; color: #6b7280; font-size: 1.1rem;
}
.fb-warning {
    background: #fef3c7; border-left: 4px solid #f59e0b;
    color: #92400e; padding: 10px 32px;
    font-size: 0.85rem; display: flex; align-items: center; gap: 8px;
}
.fb-warning strong { font-weight: 700; }
"""


def card_html(listing):
    h = html_mod.escape

    # Photo block
    if listing["img"]:
        photo = (
            f'<div class="photo">'
            f'<img src="{h(listing["img"])}" alt="" loading="lazy" '
            f'onerror="var p=this.parentElement;p.className=\'photo placeholder\';'
            f'p.innerHTML=\'📷\'"></div>'
        )
    else:
        photo = '<div class="photo placeholder">📷</div>'

    # Badges
    plat   = listing["platform"]
    color  = PLATFORM_COLORS.get(plat, "#6b7280")
    label  = PLATFORM_LABELS.get(plat, plat.upper())
    badges = f'<span class="badge" style="background:{color}">{label}</span>'
    if listing.get("is_new"):
        badges += ' <span class="badge new-badge">New</span>'
    if listing.get("is_deal"):
        badges += ' <span class="badge deal">Deal</span>'

    price = h(listing["price"]) if listing["price"] else "N/A"
    title = h(listing["title"]) if listing["title"] else "Untitled"
    url   = h(listing["url"])

    # Previously seen listings are visually dimmed per spec
    style = ' style="opacity:0.6"' if not listing.get("is_new") else ''

    return (
        f'<a href="{url}" target="_blank" rel="noopener" class="card"{style}>'
        f'{photo}'
        f'<div class="body">'
        f'<div class="badges">{badges}</div>'
        f'<div class="price">{price}</div>'
        f'<div class="title">{title}</div>'
        f'</div>'
        f'</a>'
    )


def generate_html(query, listings, platform_counts, timestamp, fb_skip=None):
    h  = html_mod.escape
    ts = h(timestamp)
    q  = h(query)
    plat_summary = " · ".join(f"{k}: {v}" for k, v in platform_counts.items() if v)

    if listings:
        cards_html = "\n    ".join(card_html(l) for l in listings)
    else:
        cards_html = '<div class="empty">No listings passed the quality filter for this search.</div>'

    fb_banner = ""
    if fb_skip:
        fb_banner = (
            f'<div class="fb-warning">'
            f'<strong>Facebook Marketplace skipped:</strong> {h(fb_skip)}'
            f'</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Marketplace Scout — {q}</title>
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>Marketplace Scout &mdash; &ldquo;{q}&rdquo;</h1>
    <p>{ts} &nbsp;&middot;&nbsp; {h(plat_summary)}</p>
  </header>
  {fb_banner}
  <main class="grid">
    {cards_html}
  </main>
  <footer>Generated by Marketplace Scout &middot; {ts}</footer>
</body>
</html>"""


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Marketplace Scout — on-demand search with HTML report"
    )
    parser.add_argument("queries",          nargs="*", help="One or more things to search for — multiple queries are merged into one report")
    parser.add_argument("--min-price",      type=float, help="Hard price floor (optional)")
    parser.add_argument("--max-price",      type=float, help="Hard price ceiling (optional)")
    parser.add_argument("--limit",          type=int,   default=15,   help="Max results to show (default: 15)")
    parser.add_argument("--platforms",      nargs="+", metavar="PLATFORM", help="Override platforms for this run (e.g. --platforms mercari depop poshmark)")
    parser.add_argument("--login-facebook", action="store_true", help="One-time Facebook login flow")
    parser.add_argument("--reset",          action="store_true", help="Wipe seen-listings history and exit")
    parser.add_argument("--list-presets",   action="store_true", help="List all saved searches and groups, then exit")
    args = parser.parse_args()

    # ── Config ─────────────────────────────────────────────────────────────────
    if CFG_PATH.exists():
        config = json.loads(CFG_PATH.read_text())
    else:
        config = DEFAULT_CONFIG.copy()
        CFG_PATH.write_text(json.dumps(config, indent=2))

    presets = config.get("presets", {})
    groups  = config.get("groups",  {})

    # --platforms flag overrides config for this run only
    if args.platforms:
        config["platforms"] = args.platforms

    # ── List presets ────────────────────────────────────────────────────────────
    if args.list_presets:
        print("\nSaved searches (presets):")
        for name, query in presets.items():
            print(f"  {name:<16} → \"{query}\"")
        if groups:
            print("\nGroups (run multiple presets at once):")
            for name, members in groups.items():
                print(f"  {name:<16} → {', '.join(members)}")
        print()
        return

    # ── Reset ──────────────────────────────────────────────────────────────────
    if args.reset:
        conn = init_db()
        conn.execute("DELETE FROM listings")
        conn.commit()
        conn.close()
        print("Seen-listings history wiped.")
        return

    # ── Playwright check ────────────────────────────────────────────────────────
    try:
        from playwright.sync_api import sync_playwright
        from playwright.async_api import async_playwright  # noqa — ensure both are installed
    except ImportError:
        print("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    # ── Facebook login flow (sync, interactive) ──────────────────────────────
    if args.login_facebook:
        with sync_playwright() as pw:
            do_facebook_login(pw)
        return

    # ── Require at least one query for normal runs ───────────────────────────
    if not args.queries:
        parser.error("at least one query is required (e.g. scout \"surfboard\" or scout surf)")

    # ── Expand presets and groups ────────────────────────────────────────────
    def expand(q):
        key = q.lower().replace(" ", "")
        if key in groups:
            return [presets[m] for m in groups[key] if m in presets]
        if key in presets:
            return [presets[key]]
        return [q]

    queries = []
    used_preset = False
    for raw in args.queries:
        expanded = expand(raw)
        if expanded != [raw]:
            used_preset = True
        queries.extend(expanded)

    limit = args.limit  # None = no cap (show all that pass quality filter)

    # ── Scrape (async parallel — all queries simultaneously) ─────────────────
    print(f"  Searching {len(queries)} quer{'y' if len(queries)==1 else 'ies'} in parallel...",
          file=sys.stderr)

    all_listings, fb_skip_reason = asyncio.run(scrape_all_async(queries, config))
    platform_counts = {}
    for l in all_listings:
        plat_key = PLATFORM_LABELS.get(l["platform"], l["platform"].upper())
        platform_counts[plat_key] = platform_counts.get(plat_key, 0) + 1

    # Deduplicate by listing ID
    seen_ids = set()
    deduped  = []
    for l in all_listings:
        if l["id"] not in seen_ids:
            seen_ids.add(l["id"])
            deduped.append(l)
    all_listings = deduped

    total_scraped = len(all_listings)

    # ── Seen-listing DB ───────────────────────────────────────────────────────
    conn = init_db()

    # ── Filter & rank ────────────────────────────────────────────────────────
    active_query = queries[0] if len(queries) == 1 else ""
    filtered = quality_filter(all_listings, query=active_query, min_price=args.min_price, max_price=args.max_price)

    # Mark each listing as new or previously seen
    for l in filtered:
        l["is_new"] = is_new(conn, l["id"])

    ranked    = rank(filtered, top_n=limit)
    new_count = sum(1 for l in ranked if l.get("is_new"))

    # ── Generate HTML ────────────────────────────────────────────────────────
    timestamp     = datetime.now().strftime("%b %d %Y  %H:%M")
    display_query = " + ".join(queries)
    html_content  = generate_html(display_query, ranked, platform_counts, timestamp, fb_skip=fb_skip_reason)
    HTML_PATH.write_text(html_content, encoding="utf-8")

    # ── Save displayed listings to DB ────────────────────────────────────────
    for l in ranked:
        save_listing(conn, l)
    conn.close()

    # ── Open in browser ──────────────────────────────────────────────────────
    subprocess.run(["open", str(HTML_PATH)], check=False)

    # ── Summary line to stdout (Claude reads this) ───────────────────────────
    print(
        f"Found {total_scraped} listings · {len(filtered)} passed quality filter "
        f"· {new_count} new · Report: {HTML_PATH}"
    )


if __name__ == "__main__":
    main()
