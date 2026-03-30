"""Page matching: pair before/after HTML files; detect renames and splits."""

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .content import extract_page_title


def find_page_pairs(before_dir, after_dir, product=None, version=None):
    """Match HTML pages between before and after by relative path.

    For Pantheon (product+version given), restricts to the expected path prefix
    en/documentation/{product}/{version}/html/ and extracts title/chapter slugs.

    For PR/generic mode (no product/version), matches all .html files and
    treats the first path component as the title slug.

    Returns list of dicts: before_path, after_path, rel_path, title_slug, chapter_slug.
    before_path or after_path may be None (new/removed pages).
    """
    before_dir = Path(before_dir)
    after_dir  = Path(after_dir)
    pairs = []

    def _parse_rel(rel):
        parts = rel.parts
        if product and version:
            html_prefix = ('en', 'documentation', product, version, 'html')
            if len(parts) <= len(html_prefix) or parts[:len(html_prefix)] != html_prefix:
                return None, None
            remaining    = parts[len(html_prefix):]
            title_slug   = remaining[0] if remaining else 'unknown'
            chapter_slug = '/'.join(remaining[1:]) if len(remaining) > 1 else 'index'
        else:
            title_slug   = parts[0].removesuffix('.html') if parts else 'unknown'
            chapter_slug = '/'.join(parts[1:]) if len(parts) > 1 else 'index'
        chapter_slug = re.sub(r'\.html?$', '', chapter_slug, flags=re.IGNORECASE)
        return title_slug, chapter_slug

    seen_rels = set()

    for before_file in sorted(before_dir.rglob('*.html')):
        rel = before_file.relative_to(before_dir)
        title_slug, chapter_slug = _parse_rel(rel)
        if title_slug is None:
            continue
        seen_rels.add(str(rel))
        after_file = after_dir / rel
        pairs.append({
            'before_path':  before_file,
            'after_path':   after_file if after_file.exists() else None,
            'rel_path':     str(rel),
            'title_slug':   title_slug,
            'chapter_slug': chapter_slug,
        })

    # After-only pages (new in preview)
    for after_file in sorted(after_dir.rglob('*.html')):
        rel = after_file.relative_to(after_dir)
        if str(rel) in seen_rels:
            continue
        title_slug, chapter_slug = _parse_rel(rel)
        if title_slug is None:
            continue
        pairs.append({
            'before_path':  None,
            'after_path':   after_file,
            'rel_path':     str(rel),
            'title_slug':   title_slug,
            'chapter_slug': chapter_slug,
        })

    _detect_renames_and_splits(pairs)
    pairs.sort(key=lambda p: (p['title_slug'], p['chapter_slug']))
    return pairs


def _detect_renames_and_splits(pairs):
    """Mutate pairs in-place: add status_hint='split'/'renamed' and remove absorbed pairs."""
    before_only = [p for p in pairs if p['after_path'] is None]
    after_only  = [p for p in pairs if p['before_path'] is None]

    if not (before_only and after_only):
        return

    from difflib import SequenceMatcher

    def _h1(path):
        try:
            return extract_page_title(path.read_text(errors='replace'))
        except Exception:
            return ''

    def _h1_similarity(a, b):
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def _strip_numbering(text):
        """Strip 'Chapter N.', '1.1.', etc. from heading text."""
        return re.sub(r'^(Chapter\s+)?\d+(\.\d+)*\.\s*', '', text, flags=re.IGNORECASE).strip()

    def _extract_h2s(html):
        """Return stripped H2 texts (section titles, not nav)."""
        soup = BeautifulSoup(html, 'html.parser')
        results = []
        for h2 in soup.select('main h2, article h2, h2'):
            raw = h2.get_text(strip=True)
            # Strip "Copy link..." anchor noise appended by Pantheon
            raw = re.sub(r'Copy\s*link.*$', '', raw, flags=re.IGNORECASE).strip()
            text = _strip_numbering(raw)
            # Skip nav cruft (short product names like "Red Hat Developer Hub")
            if text and len(text) > 10:
                results.append(text)
        return results

    after_only_by_book = {}
    for p in after_only:
        after_only_by_book.setdefault(p['title_slug'], []).append(p)

    # Cache H1s to avoid re-reading files
    h1_cache = {}
    def _cached_h1(path):
        k = str(path)
        if k not in h1_cache:
            h1_cache[k] = _h1(path)
        return h1_cache[k]

    # Pass 1: split detection (runs first — takes priority over rename)
    # A split is 1 before page whose H2 sections became N≥2 after chapters.
    matched_split_before = set()
    matched_split_after  = set()
    for bp in before_only:
        book = bp['title_slug']
        candidates = [c for c in after_only_by_book.get(book, [])
                      if id(c) not in matched_split_after]
        if len(candidates) < 2:
            continue
        try:
            before_html = bp['before_path'].read_text(errors='replace')
        except Exception:
            continue
        h2s = _extract_h2s(before_html)
        if not h2s:
            continue
        matched_candidates = []
        for ap in candidates:
            ah1 = _strip_numbering(_cached_h1(ap['after_path']))
            if not ah1:
                continue
            best_score = max((_h1_similarity(ah1, h2) for h2 in h2s), default=0.0)
            if best_score >= 0.7:
                matched_candidates.append(ap)
        if len(matched_candidates) >= 2:
            bp['status_hint'] = 'split'
            bp['split_children'] = [ap['after_path'] for ap in matched_candidates]
            matched_split_before.add(id(bp))
            for ap in matched_candidates:
                matched_split_after.add(id(ap))

    # Remove after-only pages absorbed by split detection
    pairs[:] = [p for p in pairs if not (p['before_path'] is None and id(p) in matched_split_after)]

    # Pass 2: rename detection (1-to-1 H1 similarity) on remaining unmatched pages
    matched_after = set()
    for bp in before_only:
        if id(bp) in matched_split_before:
            continue
        book = bp['title_slug']
        candidates = [c for c in after_only_by_book.get(book, [])
                      if id(c) not in matched_after and id(c) not in matched_split_after]
        if not candidates:
            continue
        bh1 = _cached_h1(bp['before_path'])
        if not bh1:
            continue
        best, best_score = None, 0.0
        for ap in candidates:
            score = _h1_similarity(bh1, _cached_h1(ap['after_path']))
            if score > best_score:
                best, best_score = ap, score
        if best is not None and best_score >= 0.7:
            bp['after_path']  = best['after_path']
            bp['status_hint'] = 'renamed'
            matched_after.add(id(best))

    # Remove after-only pages absorbed by rename detection
    pairs[:] = [p for p in pairs if not (p['before_path'] is None and id(p) in matched_after)]
