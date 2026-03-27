#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# Create/update venv if needed
if [[ ! -f venv/bin/activate ]] || [[ requirements.txt -nt venv/bin/activate ]]; then
  python3 -m venv venv
  venv/bin/pip install -q -r requirements.txt
  touch venv/bin/activate
fi

# Install Playwright Firefox browser if needed
if ! venv/bin/python -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
  echo "Installing Playwright Firefox browser..."
  venv/bin/playwright install firefox
fi

# Create ~/bin symlink
mkdir -p ~/bin
ln -sf "$REPO_ROOT/scripts/visual-diff" ~/bin/visual-diff

if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
  echo "WARNING: ~/bin is not in PATH. Add to your shell profile:" >&2
  echo "  export PATH=\"\$HOME/bin:\$PATH\"" >&2
fi

# Check .env
if [[ ! -f .env ]]; then
  echo "WARNING: .env not found. Copy .env.example to .env and fill in values." >&2
fi

echo "Setup OK."
