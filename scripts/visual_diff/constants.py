"""Shared constants: cache paths, Pantheon URLs, CSS selectors."""

from pathlib import Path

# Repo root is three levels up: constants.py → visual_diff/ → scripts/ → repo root
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / '.cache'

CONTENT_BASE = {
    'stage':   'https://content-stage.docs.redhat.com',
    'preview': 'https://content-preview.docs.redhat.com',
}

# CSS selectors tried in order to find the main content area (nav/sidebar excluded)
CONTENT_SELECTORS = [
    'main article',
    'main .pf-v5-c-content',
    '.pf-v5-c-page__main-section article',
    'main .pf-c-content',
    '.pf-c-page__main-section article',
    '#content',
    'article.doc',
    'main',
]

# Elements stripped before content text extraction (nav, menus, footers)
NAV_STRIP_SELECTORS = [
    'nav', 'header', 'footer',
    '[role="navigation"]',
    '.pf-v5-c-nav', '.pf-c-nav',
    '.pf-v5-c-page__sidebar', '.pf-c-page__sidebar',
    '.pf-v5-c-masthead', '.pf-c-masthead',
    '#toc', '.toc', '.sidebar',
    '.pf-v5-c-breadcrumb', '.pf-c-breadcrumb',
    '.feedback',
    # Prev/Next chapter navigation
    '.navfooter', '[class*="navfooter"]',
    '[class*="pagination"]', '.pf-v5-c-pagination', '.pf-c-pagination',
    'a[rel="prev"]', 'a[rel="next"]',
    # Pantheon custom web components for prev/next
    'rh-cta', '.previous-btn', '.next-btn',
]

# CSS injected into Playwright before screenshotting to hide nav/pagination elements
# (these are often inside the content area, so content_selector clipping alone isn't enough)
_SCREENSHOT_HIDE_CSS = ", ".join([
    'nav', 'header', 'footer',
    '[role="navigation"]',
    '.pf-v5-c-nav', '.pf-c-nav',
    '.pf-v5-c-page__sidebar', '.pf-c-page__sidebar',
    '.pf-v5-c-masthead', '.pf-c-masthead',
    '#toc', '.toc', '.sidebar',
    '.pf-v5-c-breadcrumb', '.pf-c-breadcrumb',
    '.feedback',
    '.navfooter', '[class*="navfooter"]',
    '[class*="pagination"]', '.pf-v5-c-pagination', '.pf-c-pagination',
    'a[rel="prev"]', 'a[rel="next"]',
    'rh-cta', '.previous-btn', '.next-btn',
]) + " { display: none !important; }\n" + \
    "main, article, main article, [role='main'] { min-height: 0 !important; height: auto !important; }"
