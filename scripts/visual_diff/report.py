"""Report generation: self-contained HTML + summary.md."""

import base64
from collections import OrderedDict
from pathlib import Path


def slugify(name):
    """Convert a name to a filesystem-safe slug."""
    slug = name.lower().replace(' ', '_')
    return ''.join(c if c.isalnum() or c in '_-' else '_' for c in slug)


def _img_to_data_uri(img_path):
    """Convert a PNG file to a base64 data URI."""
    data = Path(img_path).read_bytes()
    return f"data:image/png;base64,{base64.b64encode(data).decode()}"


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

    # Summary table
    rows = []
    for title, items in by_title.items():
        for s in items:
            chapter = s.get('chapter', '')
            status  = s.get('status', 'unknown')
            slug    = s.get('slug', slugify(title))
            if status == 'identical':
                badge, detail = '<span class="badge-identical">identical</span>', ''
            elif status == 'changed':
                pct = s.get('change_pct', 0)
                badge  = f'<span class="badge-changed">CHANGED ({pct:.1f}%)</span>'
                detail = f'<a href="#{slug}">view</a>'
            elif status == 'new':
                badge, detail = '<span class="badge-new">NEW</span>', f'<a href="#{slug}">view</a>'
            elif status == 'removed':
                badge, detail = '<span class="badge-removed">REMOVED</span>', f'<a href="#{slug}">view</a>'
            elif status == 'renamed':
                pct = s.get('change_pct', 0)
                badge  = f'<span class="badge-renamed">RENAMED ({pct:.1f}%)</span>'
                detail = f'<a href="#{slug}">view</a>'
            elif status == 'split':
                n = len(s.get('split_children', []))
                badge  = f'<span class="badge-split">SPLIT → {n} chapters</span>'
                detail = f'<a href="#{slug}">view</a>'
            elif status == 'error':
                badge, detail = '<span class="badge-error">error</span>', s.get('detail', '')
            else:
                badge, detail = '<span class="badge-skipped">skipped</span>', s.get('detail', '')
            chapter_cell = chapter if chapter else '<em>(index)</em>'
            rows.append(f'<tr><td>{title}</td><td>{chapter_cell}</td><td>{badge}</td><td>{detail}</td></tr>')

    # Counts for summary
    changed_count   = sum(1 for s in summary if s.get('status') == 'changed')
    renamed_count   = sum(1 for s in summary if s.get('status') == 'renamed')
    split_count     = sum(1 for s in summary if s.get('status') == 'split')
    new_count       = sum(1 for s in summary if s.get('status') == 'new')
    removed_count   = sum(1 for s in summary if s.get('status') == 'removed')
    identical_count = sum(1 for s in summary if s.get('status') == 'identical')
    errors_count    = sum(1 for s in summary if s.get('status') in ('error', 'skipped'))

    # Detail sections + markdown
    details  = []
    md_lines = [
        f"# Visual Diff: {label_a} vs {label_b}\n\n",
        f"**{changed_count} changed, {renamed_count} renamed, {split_count} split, "
        f"{new_count} new, {removed_count} removed** | {identical_count} identical | {errors_count} errors\n\n",
    ]

    for title, items in by_title.items():
        notable = [s for s in items if s.get('status') in ('changed', 'renamed', 'split', 'new', 'removed')]
        if not notable:
            continue

        details.append(f'<details open><summary class="title-summary">{title}</summary>')
        for s in notable:
            slug    = s.get('slug', '')
            chapter = s.get('chapter', '')
            status  = s.get('status', '')
            pct     = s.get('change_pct', 0)
            a_url   = s.get('a_url', '')
            b_url   = s.get('b_url', '')
            chapter_title = f"{title} / {chapter}" if chapter else title

            if status == 'new':
                b_png = output_dir / f"{slug}_b.png"
                b_src = _img_to_data_uri(b_png) if b_png.exists() else ''
                b_img = f'<img src="{b_src}" alt="{label_b}">' if b_src else '<em>no screenshot</em>'
                details.append(f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-new">NEW</span></h3>
              <p class="meta"><a href="{b_url}" target="_blank">{label_b}</a></p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_b}</h4>{b_img}</div>
              </div>
            </div>''')
                md_lines.append(f"## {chapter_title} *(new)*\n")
                if b_url:
                    md_lines.append(f"- [{label_b}]({b_url})\n")
                md_lines.append("\n")

            elif status == 'removed':
                a_png = output_dir / f"{slug}_a.png"
                a_src = _img_to_data_uri(a_png) if a_png.exists() else ''
                a_img = f'<img src="{a_src}" alt="{label_a}">' if a_src else '<em>no screenshot</em>'
                details.append(f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-removed">REMOVED</span></h3>
              <p class="meta"><a href="{a_url}" target="_blank">{label_a}</a></p>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a}</h4>{a_img}</div>
              </div>
            </div>''')
                md_lines.append(f"## {chapter_title} *(removed)*\n")
                if a_url:
                    md_lines.append(f"- [{label_a}]({a_url})\n")
                md_lines.append("\n")

            elif status == 'split':
                a_png = output_dir / f"{slug}_a.png"
                a_src = _img_to_data_uri(a_png) if a_png.exists() else ''
                a_img = f'<img src="{a_src}" alt="{label_a}">' if a_src else '<em>no screenshot</em>'
                children = s.get('split_children', [])
                children_html = ''.join(f'<li>{c}</li>' for c in children)
                details.append(f'''
            <div class="chapter-section" id="{slug}">
              <h3>{chapter_title} <span class="badge-split">SPLIT</span></h3>
              <p class="meta">Sections promoted to top-level chapters in {label_b}</p>
              <ul class="split-children">{children_html}</ul>
              <div class="screenshot-grid">
                <div class="screenshot-col"><h4>{label_a} (original)</h4>{a_img}</div>
              </div>
            </div>''')
                md_lines.append(f"## {chapter_title} *(split → {len(children)} chapters)*\n")
                if a_url:
                    md_lines.append(f"- [{label_a}]({a_url})\n")
                for c in children:
                    md_lines.append(f"  - {c}\n")
                md_lines.append("\n")

            elif status == 'renamed':
                a_png = output_dir / f"{slug}_a_annotated.png"
                b_png = output_dir / f"{slug}_b_annotated.png"
                if not a_png.exists():
                    a_png = output_dir / f"{slug}_a.png"
                if not b_png.exists():
                    b_png = output_dir / f"{slug}_b.png"
                a_src = _img_to_data_uri(a_png) if a_png.exists() else ''
                b_src = _img_to_data_uri(b_png) if b_png.exists() else ''
                a_img = f'<img src="{a_src}" alt="{label_a}">' if a_src else '<em>no screenshot</em>'
                b_img = f'<img src="{b_src}" alt="{label_b}">' if b_src else '<em>no screenshot</em>'
                details.append(f'''
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
            </div>''')
                md_lines.append(f"## {chapter_title} *(renamed)*\n")
                md_lines.append(f"- Change: {pct:.2f}%\n")
                if a_url:
                    md_lines.append(f"- [{label_a}]({a_url})\n")
                if b_url:
                    md_lines.append(f"- [{label_b}]({b_url})\n")
                md_lines.append("\n")

            else:  # changed
                a_png = output_dir / f"{slug}_a_annotated.png"
                b_png = output_dir / f"{slug}_b_annotated.png"
                a_src = _img_to_data_uri(a_png) if a_png.exists() else ''
                b_src = _img_to_data_uri(b_png) if b_png.exists() else ''
                a_img = f'<img src="{a_src}" alt="{label_a}">' if a_src else '<em>no screenshot</em>'
                b_img = f'<img src="{b_src}" alt="{label_b}">' if b_src else '<em>no screenshot</em>'
                details.append(f'''
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
            </div>''')
                md_lines.append(f"## {chapter_title}\n")
                md_lines.append(f"- Change: {pct:.2f}%\n")
                if a_url:
                    md_lines.append(f"- [{label_a}]({a_url})\n")
                if b_url:
                    md_lines.append(f"- [{label_b}]({b_url})\n")
                md_lines.append("\n")

        details.append('</details>')

    html = f'''<!DOCTYPE html>
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
  {changed_count} changed, {renamed_count} renamed, {split_count} split, {new_count} new,
  {removed_count} removed, {identical_count} identical, {errors_count} errors
</p>
<table>
<tr><th>Title</th><th>Chapter</th><th>Status</th><th>Details</th></tr>
{"".join(rows)}
</table>
<hr style="border:none;border-top:2px solid #e1e4e8;margin:30px 0;">
{"".join(details)}
</body></html>'''

    (output_dir / 'index.html').write_text(html, encoding='utf-8')
    (output_dir / 'summary.md').write_text(''.join(md_lines), encoding='utf-8')
