# visual-diff

Visual diff tool for Red Hat documentation. Compares Pantheon stage vs preview
environments (or PR builds) and generates an HTML report with annotated
screenshots highlighting changed regions.

## Prerequisites

- Python 3.10+
- `wget` (for mirroring documentation sites)
- VPN connection to Red Hat network (Pantheon mode)

## Setup

```bash
# First run auto-creates venv and installs dependencies
scripts/visual-diff urls
```

Or manually:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Pantheon mode (stage vs preview)

```bash
# List all title URLs
scripts/visual-diff urls --pantheon-version 1.9

# Run visual diff
scripts/visual-diff diff --pantheon-version 1.9 --headless --output /tmp/rhdh-diff/

# Filter by title
scripts/visual-diff diff --pantheon-version 1.9 --title "About" --headless
```

### PR mode (build A vs build B)

```bash
scripts/visual-diff diff --mode pr --env-a <url-a> --env-b <url-b> --output /tmp/pr-diff/
```

## How it works

1. **Mirror** both environments with `wget -r -l 2` into `.cache/mirror/`
2. **Compare text** locally (no network) to skip identical pages
3. **Render** changed pages to PNG via headless Chromium (no JS/CSS for speed)
4. **Diff** screenshots with numpy, annotate changed regions with red borders
5. **Report** collapsible HTML with side-by-side comparisons

## Configuration

Copy `.env.example` to `.env` and set:

```bash
PANTHEON_VERSION=1.9
PANTHEON_PRODUCT=red_hat_developer_hub
```
