# Visual Diff Tool — Design Spec

**Jira:** RHIDP-9152 (child of RHIDP-12898)
**Last updated:** 2026-03-30

---

## Overview

`visual-diff` is a standalone Python CLI that compares Red Hat documentation builds across environments (Pantheon stage vs preview, or any two arbitrary builds) and produces a self-contained HTML report with annotated screenshots highlighting changed regions.

The tool handles the full lifecycle: mirroring both environments, detecting structural changes (renames, splits), doing content-only text diffing to skip identical pages, rendering changed pages with headless Chromium, and producing a pixel-level visual diff report.

---

## Implementation Status

| Phase | Description | Status |
| ----- | ----------- | ------ |
| 1 | Migration from jirha + self-bootstrapping | **Done** |
| 2 | Parallel wget mirroring + two-phase CLI + content-only diff + enhanced report | **Done** |
| 3 | PR mode + rename/split detection + self-contained HTML report | **Done** |
| 4 | Claude plugin (agent + commands) | Planned |
| 5 | GitHub Action for PR comments | Planned |

---

## Architecture

```
visual-diff/
├── scripts/
│   └── visual-diff          # Single-file Python CLI (~1250 lines)
├── requirements.txt         # beautifulsoup4, Pillow, numpy, playwright, requests
├── .env.example             # PANTHEON_VERSION, PANTHEON_PRODUCT
├── .cache/                  # wget mirrors (git-ignored)
│   ├── before/              # stage (before)
│   └── after/               # preview (after)
├── reports/                 # output reports (git-ignored)
├── .claude/
│   └── plugins/
│       └── visual-diff/     # Claude plugin (Phase 4, not yet implemented)
└── action/                  # GitHub Action (Phase 5, not yet implemented)
```

The script is self-bootstrapping: it creates `venv/`, installs dependencies, and re-execs itself under the venv on first run.

---

## CLI

```text
visual-diff fetch    Mirror both environments into .cache/before/ and .cache/after/
visual-diff compare  Compare cached pages and produce HTML report + summary.md
visual-diff diff     fetch + compare (shortcut)
visual-diff urls     List available titles from both environments
```

### Common flags

| Flag | Description |
| ---- | ----------- |
| `--mode pantheon\|pr` | Comparison mode (auto-detected: `GITHUB_BASE_REF` set → `pr`, else → `pantheon`) |
| `--pantheon-version VER` | Version e.g. `1.9` (or `$PANTHEON_VERSION`) |
| `--pantheon-product PROD` | Product slug (or `$PANTHEON_PRODUCT`, default: `red_hat_developer_hub`) |
| `--env-a URL\|PATH` | Before build — URL or local path (PR mode, or `$ENV_A`) |
| `--env-b URL\|PATH` | After build — URL or local path (PR mode, or `$ENV_B`) |
| `--before-dir DIR` | Before cache dir (default: `.cache/before/`) |
| `--after-dir DIR` | After cache dir (default: `.cache/after/`) |
| `--output DIR` | Report output dir (default: `reports/`) |
| `--title FILTER` | Filter titles by substring (repeatable) |
| `--headless` | Run browser headless |
| `--output-json` | Also write `results.json` |

### Modes

**`--mode pantheon`** (default for local use): Compares Pantheon `content-stage` (before) vs `content-preview` (after). Requires VPN. Uses `wget` with `-I /en/documentation/{product}/{version}/` to restrict mirroring to the target product.

**`--mode pr`**: Compares two arbitrary builds — GitHub Pages, localhost, or local paths. No authentication needed. `--env-a` / `--env-b` required (or auto-detected from `GITHUB_EVENT_NUMBER` / `GITHUB_BASE_REF` in CI).

---

## Pipeline

### Phase 1 — Fetch

Both environments are mirrored in parallel using `ThreadPoolExecutor(max_workers=2)`. Each worker runs `wget -r -l 0 -nH --adjust-extension -I {include_path}`:

- `-l 0` — unlimited depth
- `-I {include_path}` — Pantheon mode restricts to `/en/documentation/{product}/{version}/` to avoid mirroring unrelated products
- Local paths are copied with `rsync` (or `shutil.copytree` fallback)

Output: `.cache/before/` and `.cache/after/`

### Phase 2 — Compare

#### Page matching (`find_page_pairs`)

Pages are matched by relative path. Unmatched pages trigger two detection passes:

**Pass 1 — Split detection** (runs first, takes priority):
A before page whose H2 sections match ≥2 after pages' H1 headings (fuzzy, SequenceMatcher ≥0.7) is marked `split`. The matched after pages are removed from the pool. This detects assembly pages that were restructured into separate chapter files.

**Pass 2 — Rename detection**:
Remaining unmatched before/after pages within the same book are matched by H1 similarity (SequenceMatcher ≥0.7, best-match). This detects chapter title rewording (e.g., "Setting up X" → "Set up X").

Result page statuses: `changed`, `renamed`, `split`, `new`, `removed`, `identical`

#### Content comparison

`extract_content_text()` strips nav/menus/pagination (`NAV_STRIP_SELECTORS`) before text comparison. Pages with identical content are skipped (no rendering).

#### Rendering

`_render_to_png()` uses Playwright Chromium with JS disabled (removes cookie banners, faster). Before screenshotting:

- Injects `_SCREENSHOT_HIDE_CSS` to hide nav/pagination elements that are inside the content area
- Clips to the detected content selector (`CONTENT_SELECTORS`, tried in order)
- Trims trailing whitespace rows from the PNG

#### Pixel diff

`compare_screenshots()` uses numpy to find changed pixels (threshold: channel diff > 30). Changed pixels are grouped into 50px grid cells, merged into bounding boxes with asymmetric padding (12px horizontal, 4px vertical). Annotated output: unchanged areas dimmed to 55%+45% white, changed regions at 88% original + 12% amber tint.

#### Report

`generate_report()` produces:

- `index.html` — self-contained HTML with all screenshots embedded as base64 data URIs; collapsible per-title sections; summary table
- `summary.md` — compact Markdown (changed/renamed/split/new/removed entries with links)

The output directory is cleaned before each run.

---

## Page statuses

| Status | Description | Display |
| ------ | ----------- | ------- |
| `changed` | Content differs, pixel diff > 0 | Red, with change % |
| `renamed` | Same content at different path/title | Orange |
| `split` | One before page → N after chapters (sections promoted) | Teal |
| `new` | Only in after | Blue |
| `removed` | Only in before | Purple |
| `identical` | Content match | Green |

---

## Phase 4 — Claude Plugin (planned)

A thin Claude Code plugin wrapping the CLI.

**Agent `visual-diff-agent`**: invokes `scripts/visual-diff` via Bash, interprets the report, and summarizes findings in natural language.

**Command `/visual-diff`**: runs `diff` with provided args, reports output path.

**Command `/visual-diff-urls`**: runs `urls`, prints title list.

Plugin manifest at `.claude/plugins/visual-diff/plugin.json`.

---

## Phase 5 — GitHub Action (planned)

Runs on PR open/update in `red-hat-developers-documentation-rhdh`:

1. Build PR branch: `build/scripts/build-ccutil.sh -b "pr-${{ github.event.number }}"`
2. Run `visual-diff diff --mode pr --headless` — auto-detects `--env-a` from `GITHUB_EVENT_NUMBER` and `--env-b` from `GITHUB_BASE_REF`
3. Post `summary.md` as a PR comment via `gh`

No VPN or authentication needed (ccutil builds are public GitHub Pages).
