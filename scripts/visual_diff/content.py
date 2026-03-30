"""Content extraction: text comparison ignoring nav/footer."""

from bs4 import BeautifulSoup

from .constants import CONTENT_SELECTORS, NAV_STRIP_SELECTORS


def extract_page_title(html):
    """Return the human-readable page title from the HTML (h1, then <title>)."""
    soup = BeautifulSoup(html, 'html.parser')
    h1 = soup.select_one('main h1, article h1, h1')
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.select_one('title')
    if title_tag:
        return title_tag.get_text(strip=True)
    return ''


def extract_content_text(html):
    """Extract text from the main content area only, stripping nav/footer/menus."""
    soup = BeautifulSoup(html, 'html.parser')
    for sel in NAV_STRIP_SELECTORS:
        for el in soup.select(sel):
            el.decompose()
    for sel in CONTENT_SELECTORS:
        els = soup.select(sel)
        if els:
            text = '\n'.join(el.get_text(strip=True) for el in els)
            if text.strip():
                return text
    return soup.get_text(strip=True)


def detect_content_selector(html):
    """Pick the first matching CSS selector for the content area."""
    soup = BeautifulSoup(html, 'html.parser')
    for sel in CONTENT_SELECTORS:
        if soup.select_one(sel):
            return sel
    return 'main'
