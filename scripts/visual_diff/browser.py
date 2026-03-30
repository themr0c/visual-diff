"""Browser automation: launch Chromium, render pages to PNG."""

import numpy as np
from pathlib import Path
from PIL import Image

from playwright.sync_api import sync_playwright

from .constants import _SCREENSHOT_HIDE_CSS


def open_browser(headless=True, disable_js=False):
    """Launch Chromium. disable_js blocks all JS (faster, removes cookie banners)."""
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        ignore_https_errors=True,
    )
    if disable_js:
        context.route("**/*.js", lambda route: route.abort())
    page = context.new_page()
    return p, browser, page


def _trim_whitespace(img_path, margin=8, threshold=245):
    """Crop trailing (bottom) whitespace from a PNG screenshot."""
    img = Image.open(str(img_path)).convert('RGB')
    arr = np.array(img)
    row_is_white = np.all(arr >= threshold, axis=(1, 2))
    non_white = np.where(~row_is_white)[0]
    if len(non_white) > 0:
        bottom = min(non_white[-1] + margin, arr.shape[0])
        img.crop((0, 0, img.width, bottom)).save(str(img_path))


def _render_to_png(source, output_path, page, *, content_selector=None):
    """Render HTML to a PNG screenshot.

    Args:
        source:           Path (local file) or str (URL).
        output_path:      Where to save the PNG.
        page:             Playwright page.
        content_selector: CSS selector to clip the screenshot to (None = full page).
    """
    if isinstance(source, Path):
        url = f"file://{source.resolve()}"
    else:
        url = source
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.add_style_tag(content=_SCREENSHOT_HIDE_CSS)
    if content_selector:
        try:
            el = page.locator(content_selector).first
            el.screenshot(path=str(output_path))
            _trim_whitespace(output_path)
            return
        except Exception:
            pass
    page.screenshot(path=str(output_path), full_page=True)
    _trim_whitespace(output_path)
