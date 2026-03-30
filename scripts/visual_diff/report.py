"""Report generation: self-contained HTML + summary.md."""

import base64
from collections import OrderedDict
from pathlib import Path

_NO_SCREENSHOT = '<em>no screenshot</em>'


def slugify(name):
    """Convert a name to a filesystem-safe slug."""
    slug = name.lower().replace(' ', '_')
    return ''.join(c if c.isalnum() or c in '_-' else '_' for c in slug)


def _img_to_data_uri(img_path):
    """Convert a PNG file to a base64 data URI."""
    data = Path(img_path).read_bytes()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"


def _img_tag(png_path, label):
    """Return an <img> tag with inline base64 src, or a no-screenshot placeholder."""
    p = Path(png_path)
    if p.exists():
        return f'<img src="{_img_to_data_uri(p)}" alt="{label}">'
    return _NO_SCREENSHOT


def _table_badge(status, pct, split_children):
    """Return (badge_html, detail_html) for a summary table row."""
    if status == 'identical':
        return '<span class="badge-identical">identical</span>', ''
    if status == 'changed':
        return f'<span class="badge-changed">CHANGED ({pct:.1f}%)</span>', None  # detail built by caller
    if status == 'new':
        return '<span class="badge-new">NEW</span>', None
    if status == 'removed':
        return '<span class="badge-removed">REMOVED</span>', None
    if status == 'renamed':
        return f'<span class="badge-renamed">RENAMED ({pct:.1f}%)</span>', None
    if status == 'split':
        n = len(split_children or [])
        return f'<span class="badge-split">SPLIT → {n} chapters</span>', None
    if status == 'error':
        return '<span class="badge-error">error</span>', None
    return '<span class="badge-skipped">skipped</span>', None


def _build_table_rows(by_title):
    """Return list of <tr> HTML strings for the summary table."""
    rows = []
    for title, items in by_title.items():
        for s in items:
            chapter = s.get('chapter', '')
            status  = s.get('status', 'unknown')
            slug    = s.get('slug', slugify(title))
            pct     = s.get('change_pct', 0)
            badge, _detail = _table_badge(status, pct, s.get('split_children'))

            if status == 'error':
                detail = s.get('detail', '')
            elif status in ('identical', 'skipped'):
                detail = ''
            else:
                detail = f'<a href="#{slug}">view</a>'

            chapter_cell = chapter if chapter else '<em>(index)</em>'
            rows.append(f'<tr><td>{title}</td><td>{chapter_cell}</td><td>{badge}</td><td>{detail}</td></tr>')
    return rows


def _section_new(s, output_dir, label_b):
    """Return (html_block, md_lines) for a 'new' page."""
    slug    = s.get('slug', '')
    b_url   = s.get('b_url', '')
    chapter = s.get('chapter', '')
    title   = s.get('title', '')
    chapter_title = f"{title} / {chapter}" if chapter else title
    b_img = _img_tag(output_dir / f"{slug}_b.png", label_b)
    html = f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-new">NEW</span></h3>
              <p class="meta"><a href="{b_url}" target="_blank">{label_b}</a></p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_b}</h4>{b_img}</div>
              </div>
            </div>'''
    md = [f"## {chapter_title} *(new)*\n"]
    if b_url:
        md.append(f"- [{label_b}]({b_url})\n")
    md.append("\n")
    return html, md


def _section_removed(s, output_dir, label_a):
    """Return (html_block, md_lines) for a 'removed' page."""
    slug    = s.get('slug', '')
    a_url   = s.get('a_url', '')
    chapter = s.get('chapter', '')
    title   = s.get('title', '')
    chapter_title = f"{title} / {chapter}" if chapter else title
    a_img = _img_tag(output_dir / f"{slug}_a.png", label_a)
    html = f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-removed">REMOVED</span></h3>
              <p class="meta"><a href="{a_url}" target="_blank">{label_a}</a></p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a}</h4>{a_img}</div>
              </div>
            </div>'''
    md = [f"## {chapter_title} *(removed)*\n"]
    if a_url:
        md.append(f"- [{label_a}]({a_url})\n")
    md.append("\n")
    return html, md


def _section_split(s, output_dir, label_a, label_b):
    """Return (html_block, md_lines) for a 'split' page."""
    slug     = s.get('slug', '')
    a_url    = s.get('a_url', '')
    chapter  = s.get('chapter', '')
    title    = s.get('title', '')
    children = s.get('split_children', [])
    chapter_title  = f"{title} / {chapter}" if chapter else title
    children_html  = ''.join(f'<li>{c}</li>' for c in children)
    a_img = _img_tag(output_dir / f"{slug}_a.png", label_a)
    html = f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-split">SPLIT</span></h3>
              <p class="meta">Sections promoted to top-level chapters in {label_b}</p>
              <ul class="split-children">{children_html}</ul>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a} (original)</h4>{a_img}</div>
              </div>
            </div>'''
    md = [f"## {chapter_title} *(split → {len(children)} chapters)*\n"]
    if a_url:
        md.append(f"- [{label_a}]({a_url})\n")
    for c in children:
        md.append(f"  - {c}\n")
    md.append("\n")
    return html, md


def _annotated_img_tags(output_dir, slug, label_a, label_b):
    """Return (a_img, b_img) using annotated PNGs, falling back to raw."""
    a_png = output_dir / f"{slug}_a_annotated.png"
    b_png = output_dir / f"{slug}_b_annotated.png"
    if not a_png.exists():
        a_png = output_dir / f"{slug}_a.png"
    if not b_png.exists():
        b_png = output_dir / f"{slug}_b.png"
    return _img_tag(a_png, label_a), _img_tag(b_png, label_b)


def _section_renamed(s, output_dir, label_a, label_b):
    """Return (html_block, md_lines) for a 'renamed' page."""
    slug    = s.get('slug', '')
    a_url   = s.get('a_url', '')
    b_url   = s.get('b_url', '')
    chapter = s.get('chapter', '')
    title   = s.get('title', '')
    pct     = s.get('change_pct', 0)
    chapter_title = f"{title} / {chapter}" if chapter else title
    a_img, b_img = _annotated_img_tags(output_dir, slug, label_a, label_b)
    html = f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-renamed">RENAMED</span></h3>
              <p class="meta">
                Change: {pct:.2f}% |
                <a href="{a_url}" target="_blank">{label_a}</a> |
                <a href="{b_url}" target="_blank">{label_b}</a>
              </p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a}</h4>{a_img}</div>
                <div class="screenshot-col"><h4>{label_b}</h4>{b_img}</div>
              </div>
            </div>'''
    md = [f"## {chapter_title} *(renamed)*\n", f"- Change: {pct:.2f}%\n"]
    if a_url:
        md.append(f"- [{label_a}]({a_url})\n")
    if b_url:
        md.append(f"- [{label_b}]({b_url})\n")
    md.append("\n")
    return html, md


def _section_changed(s, output_dir, label_a, label_b):
    """Return (html_block, md_lines) for a 'changed' page."""
    slug    = s.get('slug', '')
    a_url   = s.get('a_url', '')
    b_url   = s.get('b_url', '')
    chapter = s.get('chapter', '')
    title   = s.get('title', '')
    pct     = s.get('change_pct', 0)
    chapter_title = f"{title} / {chapter}" if chapter else title
    a_png = output_dir / f"{slug}_a_annotated.png"
    b_png = output_dir / f"{slug}_b_annotated.png"
    a_img = _img_tag(a_png, label_a)
    b_img = _img_tag(b_png, label_b)
    html = f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title}</h3>
              <p class="meta">
                Change: {pct:.2f}% |
                <a href="{a_url}" target="_blank">{label_a}</a> |
                <a href="{b_url}" target="_blank">{label_b}</a>
              </p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a}</h4>{a_img}</div>
                <div class="screenshot-col"><h4>{label_b}</h4>{b_img}</div>
              </div>
            </div>'''
    md = [f"## {chapter_title}\n", f"- Change: {pct:.2f}%\n"]
    if a_url:
        md.append(f"- [{label_a}]({a_url})\n")
    if b_url:
        md.append(f"- [{label_b}]({b_url})\n")
    md.append("\n")
    return html, md


_SECTION_BUILDERS = {
    'new':     _section_new,
    'removed': _section_removed,
    'split':   _section_split,
    'renamed': _section_renamed,
    'changed': _section_changed,
}


def _build_details(by_title, output_dir, label_a, label_b):
    """Return (details_html_list, md_lines) for all notable pages."""
    details  = []
    md_lines = []
    for title, items in by_title.items():
        notable = [s for s in items if s.get('status') in _SECTION_BUILDERS]
        if not notable:
            continue
        details.append(f'<details open><summary class="title-summary">{title}</summary>')
        for s in notable:
            status  = s.get('status')
            builder = _SECTION_BUILDERS[status]
            if status in ('new', 'removed'):
                html_block, md = builder(s, output_dir, label_a if status == 'removed' else label_b)
            else:
                html_block, md = builder(s, output_dir, label_a, label_b)
            details.append(html_block)
            md_lines.extend(md)
        details.append('</details>')
    return details, md_lines


_HTML_TEMPLATE = '''\
<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Visual Diff: {label_a} vs {label_b}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
          margin: 20px; background: #f6f8fa; }}
  h1 {{ color: #24292e; border-bottom: 2px solid #e1e4e8; padding-bottom: 10px; }}
  table {{ border-collapse: collapse; width: 100%; background: white;
           box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 20px 0; }}
  th, td {{ border: 1px solid #e1e4e8; padding: 12px; text-align: left; }}
  th {{ background: #f6f8fa; font-weight: 600; color: #24292e; }}
  .badge-identical {{ color: #28a745; font-weight: 500; }}
  .badge-changed   {{ color: #d73a49; font-weight: 700; }}
  .badge-new       {{ color: #0366d6; font-weight: 700; }}
  .badge-removed   {{ color: #6f42c1; font-weight: 700; }}
  .badge-renamed   {{ color: #e36209; font-weight: 700; }}
  .badge-split     {{ color: #0e7490; font-weight: 700; }}
  .split-children  {{ margin: 8px 0 12px 20px; color: #24292e; }}
  .badge-error     {{ color: #e36209; font-weight: 500; }}
  .badge-skipped   {{ color: #6a737d; font-weight: 500; }}
  details {{ background: white; border: 1px solid #e1e4e8; border-radius: 6px; margin: 20px 0; }}
  .title-summary {{ font-size: 1.2em; font-weight: 600; padding: 15px; cursor: pointer;
                    color: #0366d6; border-bottom: 1px solid #e1e4e8; }}
  .title-summary:hover {{ background: #f6f8fa; }}
  .chapter-section {{ padding: 20px; border-bottom: 1px solid #e1e4e8; }}
  .chapter-section:last-child {{ border-bottom: none; }}
  .chapter-section h3 {{ margin-top: 0; color: #24292e; }}
  .meta {{ color: #6a737d; font-size: 0.9em; margin: 10px 0; }}
  .meta a {{ color: #0366d6; text-decoration: none; }}
  .meta a:hover {{ text-decoration: underline; }}
  .screenshot-grid {{ display: flex; gap: 20px; flex-wrap: wrap; margin-top: 15px; }}
  .screenshot-col {{ flex: 1; min-width: 400px; }}
  .screenshot-col h4 {{ margin: 0 0 10px 0; color: #586069; font-size: 0.95em;
                        text-transform: uppercase; letter-spacing: 0.5px; }}
  .screenshot-col img {{ max-width: 100%; border: 1px solid #e1e4e8; border-radius: 3px;
                          box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
</style></head><body>
<h1>Visual Diff Report</h1>
<p style="color:#586069;">
  Comparing <strong>{label_a}</strong> vs <strong>{label_b}</strong> &mdash;
  {changed} changed, {renamed} renamed, {split} split, {new} new,
  {removed} removed, {identical} identical, {errors} errors
</p>
<table>
<tr><th>Title</th><th>Chapter</th><th>Status</th><th>Details</th></tr>
{rows}
</table>
<hr style="border:none;border-top:2px solid #e1e4e8;margin:30px 0;">
{details}
</body></html>'''


def generate_report(output_dir, summary, label_a="Before", label_b="After"):
    """Generate index.html (self-contained, inline images) and summary.md.

    index.html embeds all annotated PNGs as base64 data URIs so the file
    can be shared or attached without external dependencies.
    summary.md is a compact Markdown summary for pasting into Jira/GitHub comments.
    """
    output_dir = Path(output_dir)
    by_title = OrderedDict()
    for s in summary:
        title = s.get('title', s.get('name', 'Unknown'))
        by_title.setdefault(title, []).append(s)

    rows    = _build_table_rows(by_title)
    details, detail_md = _build_details(by_title, output_dir, label_a, label_b)

    changed  = sum(1 for s in summary if s.get('status') == 'changed')
    renamed  = sum(1 for s in summary if s.get('status') == 'renamed')
    split    = sum(1 for s in summary if s.get('status') == 'split')
    new      = sum(1 for s in summary if s.get('status') == 'new')
    removed  = sum(1 for s in summary if s.get('status') == 'removed')
    identical = sum(1 for s in summary if s.get('status') == 'identical')
    errors   = sum(1 for s in summary if s.get('status') in ('error', 'skipped'))

    html = _HTML_TEMPLATE.format(
        label_a=label_a, label_b=label_b,
        changed=changed, renamed=renamed, split=split,
        new=new, removed=removed, identical=identical, errors=errors,
        rows="\n".join(rows),
        details="\n".join(details),
    )

    md_lines = [
        f"# Visual Diff: {label_a} vs {label_b}\n\n",
        f"**{changed} changed, {renamed} renamed, {split} split, "
        f"{new} new, {removed} removed** | {identical} identical | {errors} errors\n\n",
        *detail_md,
    ]

    (output_dir / 'index.html').write_text(html, encoding='utf-8')
    (output_dir / 'summary.md').write_text(''.join(md_lines), encoding='utf-8')
