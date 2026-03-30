"""Pantheon / build URL helpers and HTML scraping."""

from urllib.parse import urljoin

import requests
import urllib3
from bs4 import BeautifulSoup

from .constants import CONTENT_BASE

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def splash_url(env, product, version):
    """Build the splash page URL for a product/version."""
    return f"{CONTENT_BASE[env]}/en/documentation/{product}/{version}/"


def _fetch_html(url):
    """Fetch HTML from a URL using requests."""
    resp = requests.get(url, timeout=30, verify=False)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def scrape_title_links(url, product, version):
    """Scrape title links from a Pantheon splash page."""
    soup = _fetch_html(url)
    pattern = f"/{product}/{version}/html/"
    results = []
    for a in soup.find_all('a', href=True):
        if pattern in a['href']:
            name = a.get_text(strip=True)
            if name:
                results.append((name, urljoin(url, a['href'])))
    return results


def scrape_title_links_from_build(base_url):
    """Scrape title links from a ccutil build index page."""
    url = base_url.rstrip('/') + '/index.html' if not base_url.endswith('.html') else base_url
    soup = _fetch_html(url)
    results = []
    for a in soup.find_all('a', href=True):
        name = a.get_text(strip=True)
        href = urljoin(url, a['href'])
        if name and not href.endswith('index.html'):
            results.append((name, href))
    return results
