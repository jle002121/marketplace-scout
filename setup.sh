#!/usr/bin/env bash
# Marketplace Scout — one-time setup
# Run: bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "═══════════════════════════════════════════"
echo "  Marketplace Scout — Setup"
echo "═══════════════════════════════════════════"
echo ""

# ── Install Playwright ────────────────────────────────────────────────────────
echo "▶ Installing Playwright..."
pip3 install playwright
playwright install chromium
echo "  ✓ Playwright ready"
echo ""

# ── Set up twice-daily cron ───────────────────────────────────────────────────
CRON_JOB="0 9,17 * * * cd $SCRIPT_DIR && python3 scout.py >> $SCRIPT_DIR/scout.log 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -qF "scout.py"; then
    echo "▶ Cron job already installed — skipping."
else
    echo "▶ Adding cron job (runs at 9am and 5pm daily)..."
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "  ✓ Cron installed: $CRON_JOB"
fi
echo ""

# ── Done ──────────────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════"
echo "  Setup complete!"
echo ""
echo "  Next steps:"
echo "  1. python3 $SCRIPT_DIR/scout.py --login-facebook"
echo "     (one-time — log in to Facebook in the browser that opens)"
echo ""
echo "  2. python3 $SCRIPT_DIR/scout.py"
echo "     (run any time; cron also runs at 9am and 5pm)"
echo "═══════════════════════════════════════════"
echo ""
