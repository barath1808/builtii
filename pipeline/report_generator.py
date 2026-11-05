"""Portable review report and spreadsheet-safe CSV, no external assets."""
import csv
from html import escape
from pathlib import Path


def safe_cell(value):
    text = str(value if value is not None else "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def write_report(folder, report):
    folder = Path(folder)
    with (folder / "quantities.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["observation_id", "page", "item", "AI1 quantity", "AI2 quantity", "unit", "status", "review reasons"])
        for r in report["rows"]:
            writer.writerow([safe_cell(x) for x in [r["id"], r["page"], r["description"], r["quantity"], r["ai2_quantity"],
                                                   r["unit"], r["status"], "; ".join(r["reasons"])]])
    h = lambda value: escape(str(value if value is not None else "—"), quote=True)
    rows = []
    for r in report["rows"]:
        evidence = []
        for stage in ("ai1", "ai2"):
            item = r[stage]
            if not item:
                continue
            evidence.append(f"<h4>{stage.upper()} evidence</h4><p>{h(item['measurement']['explanation'])}</p>")
            for source in item["evidence"]:
                evidence.append(f"<blockquote>{h(source['quote'])}</blockquote><p>{h(source['location'])}</p>")
                if source["bbox"]:
                    x, y, x2, y2 = source["bbox"]
                    evidence.append(f'<div class="drawing"><img loading="lazy" alt="Drawing page {r["page"]}" src="previews/{r["page"]}.png">'
                                    f'<span class="box" style="left:{x*100}%;top:{y*100}%;width:{(x2-x)*100}%;height:{(y2-y)*100}%"></span></div>')
            evidence.append(f"<pre>{h(str(item['scope']))}</pre>")
        reasons = "".join(f"<li>{h(reason)}</li>" for reason in r["reasons"])
        rows.append(f'<tr data-status="{r["status"]}"><td>{h(r["id"])}</td><td>{r["page"]}</td><td>{h(r["description"])}</td>'
                    f'<td>{h(r["quantity"])}</td><td>{h(r["ai2_quantity"])}</td><td>{h(r["unit"])}</td><td class="{r["status"]}">{h(r["status"].replace("_"," "))}</td>'
                    f'<td><details><summary>Evidence &amp; review</summary><ul>{reasons}</ul>{"".join(evidence)}</details></td></tr>')
    region_entries = []
    for r in report["review_regions"]:
        preview = ""
        if r["bbox"]:
            x, y, x2, y2 = r["bbox"]
            preview = (f'<details><summary>Locate region</summary><div class="drawing">'
                       f'<img loading="lazy" alt="Review region on page {r["page"]}" src="previews/{r["page"]}.png">'
                       f'<span class="box" style="left:{x*100}%;top:{y*100}%;width:{(x2-x)*100}%;height:{(y2-y)*100}%"></span></div></details>')
        region_entries.append(f'<li>Page {r["page"]}, {h(r["stage"])}: {h(r["reason"])}; bounds {h(r["bbox"])} '
                              f'<a href="previews/{r["page"]}.png">view page</a>{preview}</li>')
    regions = "".join(region_entries)
    errors = "".join(f'<li>Page {e["page"]}, {h(e["stage"])}: {h(e["message"])}</li>' for e in report["errors"])
    summary = report["summary"]
    html = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Builtii drawing review</title><style>
body{{font:15px system-ui;background:#f5f7fb;color:#193047;margin:30px}}h1{{margin-bottom:5px}}a{{color:#166b83}}
.notice{{padding:18px;background:#fff0cf;border-left:4px solid #b36c00}}.stats{{display:flex;gap:25px;padding:24px 0;flex-wrap:wrap}}
table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:12px;border-bottom:1px solid #dce3e9;text-align:left;vertical-align:top}}
th{{background:#e5edf3}}.supported{{color:#176541}}.review_required{{color:#985600}}details{{min-width:220px;max-width:650px}}blockquote{{margin:10px 0;padding:10px;background:#f2f6f8}}
.drawing{{position:relative;line-height:0}}.drawing img{{width:100%}}.box{{position:absolute;border:2px solid #ef3f2b;box-sizing:border-box;background:#ff55001a}}
pre{{white-space:pre-wrap}}input,select{{padding:10px;margin:10px 10px 20px 0}}.scroll{{overflow:auto}}[hidden]{{display:none!important}}
</style><h1>Builtii / Drawing review</h1><p>Source SHA-256: {h(report['source_sha256'])}</p>
<p class="notice">{h(report['notice'])}</p><div class="stats"><b>{summary['observations']} observations</b><b>{summary['supported']} supported</b>
<b>{summary['review_required']} need human review</b><b>{summary['ai1_pages']}/{summary['pages']} AI1 pages · {summary['ai2_pages']}/{summary['pages']} AI2 pages</b></div>
<p>Processing: {"complete" if report['processing_complete'] else "INCOMPLETE — some pages failed"}. Accuracy: unmeasured.</p>
<a href="quantities.csv">Download quantity table (CSV)</a> · <a href="report.json">Full evidence (JSON)</a>
<h2>Page and region review queue</h2><ul>{regions or '<li>No regions reported by the models; completeness still requires review.</li>'}{errors}</ul>
<h2>Items and quantities</h2><input id="search" placeholder="Search items or pages" aria-label="Search observations"><select id="filter" aria-label="Filter status"><option value="">All observations</option><option value="review_required">Human review required</option><option value="supported">Supported by both extractions</option></select>
<div class="scroll"><table><thead><tr><th>ID</th><th>Page</th><th>Item</th><th>AI1 quantity</th><th>AI2 quantity</th><th>Unit</th><th>Status</th><th>Source evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<script>const search=document.getElementById('search'),filter=document.getElementById('filter');function apply(){{for(const row of document.querySelectorAll('tbody tr'))row.hidden=!!((filter.value&&row.dataset.status!==filter.value)||!row.textContent.toLowerCase().includes(search.value.toLowerCase()));}}search.addEventListener('input',apply);filter.addEventListener('change',apply);</script></html>'''
    (folder / "report.html").write_text(html, encoding="utf-8")
