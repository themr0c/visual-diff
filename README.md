# visual-diff

Visual diff tool for Red Hat documentation. Compares Pantheon stage vs preview
environments (or arbitrary builds) and generates a self-contained HTML report
with annotated screenshots highlighting changed regions.

## Prerequisites

- Python 3.10+
- `wget` (Pantheon mode)
- VPN connection to Red Hat network (Pantheon mode)

## Setup

The script is self-bootstrapping — running it directly creates the venv and installs
dependencies on first use:

```bash
scripts/visual-diff urls --pantheon-version 1.9
```

Optionally set defaults in `.env`:

```bash
cp .env.example .env   # set PANTHEON_VERSION and PANTHEON_PRODUCT
```

## Commands

```text
visual-diff fetch    Mirror both environments into .cache/before/ and .cache/after/
visual-diff compare  Compare cached pages and produce report
visual-diff diff     fetch + compare (shortcut)
visual-diff urls     List available titles from both environments
```

### Pantheon mode (stage vs preview)

```bash
# One-shot: fetch and compare
visual-diff diff --pantheon-version 1.9

# Two-phase: fetch once, re-run compare with different options
visual-diff fetch --pantheon-version 1.9
visual-diff compare --title "audit"

# List titles
visual-diff urls --pantheon-version 1.9
```

### PR mode (build A vs build B)

```bash
visual-diff diff --mode pr --env-a ./build/ --env-b https://example.com/ --output reports/
visual-diff urls --mode pr --env-a ./build/ --env-b https://example.com/
```

## Output

Reports go to `reports/` by default (`--output` to change):

- `index.html` — self-contained report with all screenshots embedded as base64 (attach to Jira, open offline)
- `summary.md` — compact Markdown for GitHub PR comments
- `raw_screenshots/{slug}_a.png` / `raw_screenshots/{slug}_b.png` — raw screenshots
- `annotated_screenshots/{slug}_a_annotated.png` / `annotated_screenshots/{slug}_b_annotated.png` — annotated (changed regions highlighted)

## How it works

1. **Fetch** — mirrors both environments with `wget` into `.cache/before/` and `.cache/after/` in parallel
2. **Match** — pairs pages by relative path; detects renamed chapters (fuzzy H1 matching) and split assemblies (sections promoted to chapters)
3. **Text diff** — compares content-only text (nav/menus stripped) to skip identical pages
4. **Render** — screenshots changed pages via headless Chromium with JS disabled
5. **Pixel diff** — numpy diff, changed regions annotated with amber highlight and dimmed surroundings
6. **Report** — self-contained HTML with collapsible per-title sections; page statuses: changed, renamed, split, new, removed
