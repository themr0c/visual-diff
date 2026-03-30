"""CLI commands: urls, fetch, compare, diff, and argparse main()."""

import json
import os
import shutil
import sys
import time
import argparse
from pathlib import Path

from .constants import CACHE_DIR, CONTENT_BASE
from .urls import splash_url, scrape_title_links, scrape_title_links_from_build
from .fetch import resolve_pr_envs, resolve_before_after_urls, fetch_parallel
from .matching import find_page_pairs
from .content import extract_content_text, extract_page_title, detect_content_selector
from .browser import open_browser, _render_to_png
from .compare import compare_screenshots
from .report import generate_report, slugify


def cmd_urls(args):
    """List available titles from both environments."""
    if args.mode == "pr":
        env_a, env_b = resolve_pr_envs(args)
        print(f"Before (env-a): {env_a}")
        print(f"After  (env-b): {env_b}\n")
        a_links = scrape_title_links_from_build(env_a)
        b_links = scrape_title_links_from_build(env_b)
        a_by_name = dict(a_links)
        b_by_name = dict(b_links)
        all_names = sorted(set(list(a_by_name) + list(b_by_name)))
        if args.title:
            all_names = [n for n in all_names if any(t.lower() in n.lower() for t in args.title)]
        results = [{'name': n, 'before': a_by_name.get(n, ''), 'after': b_by_name.get(n, '')}
                   for n in all_names]
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"{r['name']}\n  before: {r['before'] or 'N/A'}\n  after:  {r['after'] or 'N/A'}\n")
            print(f"Total: {len(results)} titles")
    else:
        stage   = splash_url('stage',   args.pantheon_product, args.pantheon_version)
        preview = splash_url('preview', args.pantheon_product, args.pantheon_version)
        print(f"Before (stage):   {stage}")
        print(f"After  (preview): {preview}\n")
        stage_links   = scrape_title_links(stage,   args.pantheon_product, args.pantheon_version)
        preview_links = scrape_title_links(preview, args.pantheon_product, args.pantheon_version)
        stage_by_name   = dict(stage_links)
        preview_by_name = dict(preview_links)
        all_names = sorted(set(list(stage_by_name) + list(preview_by_name)))
        if args.title:
            all_names = [n for n in all_names if any(t.lower() in n.lower() for t in args.title)]
        results = [{'name': n, 'before': stage_by_name.get(n, ''), 'after': preview_by_name.get(n, '')}
                   for n in all_names]
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"{r['name']}\n  before (stage):   {r['before'] or 'N/A'}\n  after  (preview): {r['after'] or 'N/A'}\n")
            print(f"Total: {len(results)} titles")


def cmd_fetch(args):
    """Phase 1: Mirror both environments into before_dir and after_dir (parallel)."""
    before_dir = Path(args.before_dir)
    after_dir  = Path(args.after_dir)
    before_url, after_url = resolve_before_after_urls(args)

    include_path = None
    if args.mode == 'pantheon':
        include_path = f"/en/documentation/{args.pantheon_product}/{args.pantheon_version}/"

    print(f"Fetching before: {before_url}")
    print(f"         → {before_dir}")
    print(f"Fetching after:  {after_url}")
    print(f"         → {after_dir}")
    t0 = time.time()
    fetch_parallel(before_url, after_url, before_dir, after_dir, include_path=include_path)
    print(f"Fetch complete in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# cmd_compare helpers (each handles one page status variant)
# ---------------------------------------------------------------------------

def _validate_compare_args(args, before_dir, after_dir):
    """Exit with an error message if compare pre-conditions are not met."""
    if not before_dir.exists() or not after_dir.exists():
        sys.exit(
            f"Cache dirs not found — run 'fetch' first.\n"
            f"  before: {before_dir}\n"
            f"  after:  {after_dir}"
        )
    if args.mode == 'pantheon':
        if not getattr(args, 'pantheon_version', None):
            sys.exit("Error: --pantheon-version (or $PANTHEON_VERSION) required for compare in pantheon mode")
        if not getattr(args, 'pantheon_product', None):
            sys.exit("Error: --pantheon-product (or $PANTHEON_PRODUCT) required for compare in pantheon mode")


def _build_urls(pair, is_pantheon):
    """Return (a_url, b_url) strings for the pair."""
    before_path = pair['before_path']
    after_path  = pair['after_path']
    if is_pantheon:
        a_url = f"{CONTENT_BASE['stage']}/{pair['rel_path']}"   if before_path else ''
        b_url = f"{CONTENT_BASE['preview']}/{pair['rel_path']}" if after_path  else ''
    else:
        a_url = str(before_path) if before_path else ''
        b_url = str(after_path)  if after_path  else ''
    return a_url, b_url


def _process_split(pair, title, chapter, slug, a_url, b_url, output_dir, page, html):
    """Screenshot a split page and return a summary entry dict."""
    before_path = pair['before_path']
    content_sel = detect_content_selector(html)
    a_path = output_dir / 'raw_screenshots' / f"{slug}_a.png"
    try:
        _render_to_png(before_path, a_path, page, content_selector=content_sel)
        children = []
        for cp in pair.get('split_children', []):
            try:
                children.append(extract_page_title(cp.read_text(errors='replace')) or str(cp.name))
            except Exception:
                children.append(str(cp.name))
        print(f"  SPLIT → {len(children)} chapters")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'split', 'split_children': children}
    except Exception as e:
        print(f"  ERROR: {e}")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'error', 'detail': str(e)}


def _process_new_or_removed(pair, title, chapter, slug, a_url, b_url, output_dir, page, content_sel):
    """Screenshot a new or removed page and return a summary entry dict."""
    before_path = pair['before_path']
    after_path  = pair['after_path']
    status = 'new' if before_path is None else 'removed'
    src    = after_path if before_path is None else before_path
    raw_dir  = output_dir / 'raw_screenshots'
    out_path = (raw_dir / f"{slug}_b.png") if status == 'new' else (raw_dir / f"{slug}_a.png")
    try:
        _render_to_png(src, out_path, page, content_selector=content_sel)
        print(f"  {status.upper()}")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': status}
    except Exception as e:
        print(f"  ERROR: {e}")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'error', 'detail': str(e)}


def _read_pair_content(pair):
    """Read before/after HTML; return (before_html, before_text, after_text, chapter)."""
    before_path = pair['before_path']
    after_path  = pair['after_path']
    before_html = before_path.read_text(errors='replace')
    after_html  = after_path.read_text(errors='replace')
    before_text = extract_content_text(before_html)
    after_text  = extract_content_text(after_html)
    chapter = extract_page_title(before_html) or extract_page_title(after_html) or None
    return before_html, before_text, after_text, chapter


def _process_changed_or_renamed(pair, title, chapter, slug, a_url, b_url,
                                 output_dir, page, before_html):
    """Render, diff, and annotate a changed/renamed page. Return summary entry dict."""
    before_path = pair['before_path']
    after_path  = pair['after_path']
    is_rename   = pair.get('status_hint') == 'renamed'
    content_sel = detect_content_selector(before_html)
    raw_dir = output_dir / 'raw_screenshots'
    ann_dir = output_dir / 'annotated_screenshots'
    try:
        a_path = raw_dir / f"{slug}_a.png"
        b_path = raw_dir / f"{slug}_b.png"
        _render_to_png(before_path, a_path, page, content_selector=content_sel)
        _render_to_png(after_path,  b_path, page, content_selector=content_sel)

        if is_rename:
            _, change_pct = compare_screenshots(a_path, b_path, ann_dir, slug)
            status = 'renamed'
            print(f"  RENAMED ({change_pct:.2f}%)")
        else:
            status, change_pct = compare_screenshots(a_path, b_path, ann_dir, slug)
            print(f"  {'CHANGED' if status == 'changed' else status}"
                  + (f" ({change_pct:.2f}%)" if status == 'changed' else ''))
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': status, 'change_pct': change_pct}
    except Exception as e:
        print(f"  ERROR: {e}")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'error', 'detail': str(e)}


def _process_pair(pair, i, total, is_pantheon, output_dir, page):
    """Dispatch one page pair to the appropriate handler. Returns a summary entry dict."""
    title = pair['title_slug'].replace('_', ' ').title()
    slug  = slugify(f"{pair['title_slug']}_{pair['chapter_slug']}")
    a_url, b_url = _build_urls(pair, is_pantheon)

    if pair.get('status_hint') == 'split':
        html = pair['before_path'].read_text(errors='replace')
        chapter = extract_page_title(html) or None
        print(f"[{i}/{total}] {title + ' / ' + chapter if chapter else title}")
        return _process_split(pair, title, chapter, slug, a_url, b_url, output_dir, page, html)

    if pair['before_path'] is None or pair['after_path'] is None:
        src = pair['after_path'] if pair['before_path'] is None else pair['before_path']
        html = src.read_text(errors='replace')
        chapter = extract_page_title(html) or None
        content_sel = detect_content_selector(html)
        print(f"[{i}/{total}] {title + ' / ' + chapter if chapter else title}")
        return _process_new_or_removed(pair, title, chapter, slug, a_url, b_url, output_dir, page, content_sel)

    # Both sides present — read content and compare text first
    try:
        before_html, before_text, after_text, chapter = _read_pair_content(pair)
    except Exception as e:
        print(f"  ERROR reading: {e}")
        return {'title': title, 'chapter': None, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'error', 'detail': str(e)}

    display = f"{title} / {chapter}" if chapter else title
    print(f"[{i}/{total}] {display}")

    is_rename = pair.get('status_hint') == 'renamed'
    if before_text == after_text and not is_rename:
        print("  identical (content match)")
        return {'title': title, 'chapter': chapter, 'slug': slug,
                'a_url': a_url, 'b_url': b_url, 'status': 'identical', 'change_pct': 0.0}

    return _process_changed_or_renamed(pair, title, chapter, slug, a_url, b_url,
                                       output_dir, page, before_html)


def cmd_compare(args):
    """Phase 2: Compare mirrored pages and produce HTML report + summary.md."""
    before_dir = Path(args.before_dir)
    after_dir  = Path(args.after_dir)
    _validate_compare_args(args, before_dir, after_dir)

    output_dir = Path(args.output)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    (output_dir / 'raw_screenshots').mkdir()
    (output_dir / 'annotated_screenshots').mkdir()

    is_pantheon = (args.mode == 'pantheon')
    product = getattr(args, 'pantheon_product', None)
    version = getattr(args, 'pantheon_version', None)

    pairs = find_page_pairs(
        before_dir, after_dir,
        product=product if is_pantheon else None,
        version=version if is_pantheon else None,
    )

    if args.title:
        pairs = [p for p in pairs if any(t.lower() in p['title_slug'].lower() for t in args.title)]

    print(f"Found {len(pairs)} matching pages")

    p, browser, page = open_browser(headless=True, disable_js=is_pantheon)
    try:
        summary = [
            _process_pair(pair, i + 1, len(pairs), is_pantheon, output_dir, page)
            for i, pair in enumerate(pairs)
        ]
    finally:
        browser.close()
        p.stop()

    label_a = "Stage (before)"  if is_pantheon else "Before"
    label_b = "Preview (after)" if is_pantheon else "After"
    generate_report(output_dir, summary, label_a, label_b)

    if args.output_json:
        (output_dir / 'results.json').write_text(json.dumps(summary, indent=2))

    changed  = sum(1 for s in summary if s.get('status') == 'changed')
    renamed  = sum(1 for s in summary if s.get('status') == 'renamed')
    split    = sum(1 for s in summary if s.get('status') == 'split')
    new      = sum(1 for s in summary if s.get('status') == 'new')
    removed  = sum(1 for s in summary if s.get('status') == 'removed')
    identical = sum(1 for s in summary if s.get('status') == 'identical')
    errors   = sum(1 for s in summary if s.get('status') in ('error', 'skipped'))
    print(f"\nDone. Changed: {changed}, Renamed: {renamed}, Split: {split}, "
          f"New: {new}, Removed: {removed}, Identical: {identical}, Errors: {errors}")
    print(f"Report:  {output_dir / 'index.html'}")
    print(f"Summary: {output_dir / 'summary.md'}")


def cmd_diff(args):
    """Fetch both environments then compare (shortcut for fetch + compare)."""
    cmd_fetch(args)
    cmd_compare(args)


def main():
    """Entry point: parse args and dispatch to command handler."""
    parser = argparse.ArgumentParser(
        description="Visual diff tool for documentation builds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  pantheon  Compare Pantheon stage (before) vs preview (after). Requires VPN.
  pr        Compare two arbitrary builds (ccutil output, GitHub Pages, localhost).

Examples:
  visual-diff diff --pantheon-version 1.9 --output /tmp/diff-output/
  visual-diff fetch --pantheon-version 1.9
  visual-diff compare --output /tmp/diff-output/
  visual-diff diff --mode pr --env-a ./build/ --env-b https://example.com/ --output /tmp/pr-diff/
  visual-diff urls --pantheon-version 1.9
""",
    )

    parser.add_argument(
        "--mode", choices=["pantheon", "pr"],
        help="Comparison mode (default: auto-detect from GITHUB_BASE_REF)",
    )

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--title", action="append",
                        help="Filter titles by substring (repeatable)")

    pantheon_opts = argparse.ArgumentParser(add_help=False)
    pantheon_opts.add_argument(
        "--pantheon-product", default=os.getenv("PANTHEON_PRODUCT"),
        help="Product slug (default: $PANTHEON_PRODUCT)",
    )
    pantheon_opts.add_argument(
        "--pantheon-version", default=os.getenv("PANTHEON_VERSION"),
        help="Product version e.g. 1.9 (default: $PANTHEON_VERSION)",
    )

    pr_opts = argparse.ArgumentParser(add_help=False)
    pr_opts.add_argument("--env-a", default=os.getenv("ENV_A"),
                         help="Before build: URL or local path (default: $ENV_A)")
    pr_opts.add_argument("--env-b", default=os.getenv("ENV_B"),
                         help="After build: URL or local path (default: $ENV_B)")

    cache_opts = argparse.ArgumentParser(add_help=False)
    cache_opts.add_argument("--before-dir", default=str(CACHE_DIR / 'before'),
                            help=f"Before cache dir (default: {CACHE_DIR / 'before'})")
    cache_opts.add_argument("--after-dir",  default=str(CACHE_DIR / 'after'),
                            help=f"After cache dir (default: {CACHE_DIR / 'after'})")

    output_opts = argparse.ArgumentParser(add_help=False)
    output_opts.add_argument("--output", "-o", default="reports",
                             help="Output directory (default: reports/)")
    output_opts.add_argument("--output-json", action="store_true",
                             help="Also write results.json")

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_urls = subparsers.add_parser("urls", parents=[common, pantheon_opts, pr_opts],
                                   help="List available titles from both environments")
    p_urls.add_argument("--json", action="store_true", help="Output as JSON")

    subparsers.add_parser("fetch", parents=[pantheon_opts, pr_opts, cache_opts],
                          help="Mirror both environments into .cache/before/ and .cache/after/")

    subparsers.add_parser("compare", parents=[common, pantheon_opts, cache_opts, output_opts],
                          help="Compare cached pages and produce HTML report + summary.md")

    subparsers.add_parser("diff", parents=[common, pantheon_opts, pr_opts, cache_opts, output_opts],
                          help="Fetch then compare (shortcut)")

    args = parser.parse_args()

    if not args.mode:
        args.mode = "pr" if os.getenv("GITHUB_BASE_REF") else "pantheon"

    if args.mode == "pantheon" and args.command in ("fetch", "diff", "urls"):
        if not args.pantheon_version:
            parser.error("Pantheon mode requires --pantheon-version or $PANTHEON_VERSION")

    handlers = {
        "urls":    cmd_urls,
        "fetch":   cmd_fetch,
        "compare": cmd_compare,
        "diff":    cmd_diff,
    }
    handlers[args.command](args)
