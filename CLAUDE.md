# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this tool does

`visual-diff` is a single-file Python CLI that compares Red Hat documentation builds visually. It mirrors two environments, diffs page content to skip identical pages, screenshots changed pages via headless Chromium, and produces a self-contained HTML report with annotated side-by-side comparisons.

## Setup

The script is self-bootstrapping: running `scripts/visual-diff` directly creates the venv and re-execs itself under it if needed. No separate setup step required.

```bash
cp .env.example .env  # set PANTHEON_VERSION and PANTHEON_PRODUCT
```

## Running

```bash
# Fetch + compare in one shot
scripts/visual-diff diff --pantheon-version 1.9

# Two-phase (re-run compare without re-fetching)
scripts/visual-diff fetch --pantheon-version 1.9
scripts/visual-diff compare --title "audit"

# PR mode
scripts/visual-diff diff --mode pr --env-a ./build/ --env-b https://example.com/

# List titles
scripts/visual-diff urls --pantheon-version 1.9
```

## Architecture

The entry point is `scripts/visual-diff` (thin bootstrap). Logic lives in the `scripts/visual_diff/` package.

**Two comparison modes:**

- `--mode pantheon` (default): Compares Pantheon `content-stage` vs `content-preview`. Mirrors HTML with `wget` into `.cache/before/` and `.cache/after/`, restricting to the product/version path (`-I /en/documentation/{product}/{version}/`). Requires VPN.
- `--mode pr`: Compares two arbitrary builds (GitHub Pages, localhost, local path). Mirrors with `wget` or copies local directories.

**Mode auto-detection:** `GITHUB_BASE_REF` set → `pr` mode; otherwise → `pantheon` mode.

**Pipeline:**

1. `fetch_parallel()` — mirrors both environments in parallel via `ThreadPoolExecutor` → `.cache/before/` and `.cache/after/`
2. `find_page_pairs()` — matches pages by relative path; then runs two detection passes:
   - Pass 1 (split): before page with H2 sections matching ≥2 after pages' H1s → `status_hint='split'`
   - Pass 2 (rename): remaining unmatched before/after pages with H1 similarity ≥0.7 → `status_hint='renamed'`
3. Content-only text comparison via `extract_content_text()` (strips nav/menus/pagination using `NAV_STRIP_SELECTORS`) — skips identical pages
4. `_render_to_png()` — Playwright Chromium with JS disabled; injects `_SCREENSHOT_HIDE_CSS` to hide nav/pagination; clips to content selector; trims trailing whitespace
5. `compare_screenshots()` — numpy pixel diff, merges changed cells into bounding boxes with asymmetric padding (12px H / 4px V), annotates with amber tint + dimming
6. `generate_report()` — self-contained `index.html` (all PNGs base64-embedded) + `summary.md`

**Page statuses:** `changed`, `renamed`, `split` (assembly split into chapters), `new`, `removed`, `identical`

**Key constants:**

- `CACHE_DIR` = `.cache/` (mirrors go here, git-ignored)
- `CONTENT_BASE` = dict with `stage` and `preview` Pantheon base URLs
- `CONTENT_SELECTORS` = CSS selectors tried in order to find main content area
- `NAV_STRIP_SELECTORS` / `_SCREENSHOT_HIDE_CSS` = elements stripped from text extraction / hidden before screenshotting

**Output files** (in `--output` dir, default `reports/`, git-ignored):

- `index.html` — self-contained HTML with base64-embedded screenshots (shareable as a single file)
- `summary.md` — compact Markdown for GitHub/Jira comments
- `{slug}_a.png` / `{slug}_b.png` — raw screenshots
- `{slug}_a_annotated.png` / `{slug}_b_annotated.png` — annotated screenshots

## Dependencies

Managed via `venv/` (git-ignored). See `requirements.txt`: `beautifulsoup4`, `Pillow`, `numpy`, `playwright`, `requests`. External: `wget`.
