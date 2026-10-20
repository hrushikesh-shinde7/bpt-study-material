#!/usr/bin/env python3
"""Build the printable A4 short notes for Neuro or Community, in the same
format as tools/print_short.py (CVR).

Each sheet lives in src/<subject>/short/<slug>.html, with the same slug as the
full page it condenses: a small metadata comment (pages: the page budget,
title: optional) followed by the sheet's boxes (<p class="ask"> and
<section class="b b--p|n|a|c|x">). Each sheet shows the page of its topic in
the subject's full-notes PDF, so build that first (tools/print_subject.py),
then:

    python tools/print_subject_short.py neuro [output.pdf]
    python tools/print_subject_short.py community [output.pdf]

Inside a sheet, <a href="#slug">text</a> becomes "text (p. N)" pointing at
that sheet.
"""
import html
import importlib
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import print_pdf as pp  # noqa: E402
import print_short as ps  # noqa: E402
import print_subject as psub  # noqa: E402
import print_subject_answers as psa  # noqa: E402


def esc(s):
    return html.escape(s, quote=True)


def sheets(mod):
    """(part, slug, code, title, note, budget, body) for every written sheet, in syllabus order."""
    out = []
    for slug, code, title, part, note in mod.PAGES:
        f = mod.SRC / "short" / f"{slug}.html"
        if f.exists():
            meta, body = ps.parse(f)
            out.append((part, slug, code, meta.get("title", title), note, int(meta.get("pages", "1")), body))
    return out


def checked_date(mod):
    """Latest 'date:' among the subject's full pages."""
    dates = []
    for f in mod.SRC.glob("*.html"):
        meta, _ = build.parse_source(f)
        try:
            dates.append(datetime.strptime(meta.get("date", ""), "%d %B %Y"))
        except ValueError:
            pass
    return f"{max(dates).day} {max(dates):%B %Y}" if dates else ""


def build_html(doc, cfg, mod, items, full_pages):
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>{esc(cfg['name'])}: short notes</title>
<link rel="stylesheet" href="{(build.ROOT / "assets" / "notes.css").as_uri()}">
<style>{ps.SHORT_CSS}</style>
</head>
<body class="print">
"""
    parts = {p[0]: p for p in mod.PARTS}
    known = {slug for _, slug, *_ in items}

    def part_label(key):
        return f"Part {key}: {parts[key][1]}" if key != "E" else parts[key][1]

    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>{esc(cfg['name'])}</h1>
    <p class="cover__sub">Short notes for revision: one sheet per topic, in syllabus order, with the page of the full notes for each.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Sheets</dt><dd>{len(items)} sheets: every topic in the syllabus, then the exam skills</dd>
    <dt>Built from</dt><dd>The full notes and the 20 MUHS question papers, Summer 2016 to Summer 2026 (code {cfg['code']})</dd>
    <dt>Content checked</dt><dd>{checked_date(mod)}</dd>
    <dt>Online version</dt><dd>{pp.SITE_URL}{cfg['folder']}/</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Sources for every fact are listed in the full notes.</p>
</section>"""

    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use the short notes</h1>
  <p>These sheets are for revision, after you have read a topic once in the full notes. Each topic has its own sheet of one to three pages, in the same order as the full notes.</p>
  <ol>
    <li><b>Read the yellow line first.</b> It says how the topic is asked in the MUHS paper.</li>
    <li><b>Cover a box and recall it,</b> then check. Bold words and numbers are the ones to write in the answer.</li>
    <li><b>Tick a square at the top right of a sheet</b> each time you revise it. Aim for day 1, day 7 and day 21.</li>
    <li><b>Need more?</b> Each sheet gives the page of the same topic in the full notes.</li>
  </ol>
  <h2>What the colours mean</h2>
  <div class="key">
    <section class="b"><h3>Grey</h3><p>Definitions, types, medical and surgical management</p></section>
    <section class="b b--p"><h3>Orange</h3><p>Disease process, clinical features and the problems they cause</p></section>
    <section class="b b--n"><h3>Blue</h3><p>Investigations, scales and normal values</p></section>
    <section class="b b--a"><h3>Green</h3><p>Physiotherapy: assessment, ICF, goals, treatment and doses</p></section>
    <section class="b b--c"><h3>Amber</h3><p>Precautions, contraindications, stop criteria and complications</p></section>
    <section class="b b--x"><h3>Yellow</h3><p>Exam plan: answer structure, what to draw, keywords</p></section>
  </div>
  <p class="ask"><b>The paper (20 papers, 2016–2026):</b> 80 marks in 3 hours. Short answers: any 5 of 6 at 3 marks and any 5 of 6 at 7 marks. Long answers: two questions, each any 1 of 2 at 15 marks. {esc(cfg['cases'])}</p>
</section>"""

    toc = ['<section class="toc-print">', "  <h1>Contents</h1>", '  <div class="toc-cols">']
    cur = None
    for part, slug, code, title, *_ in items:
        if part != cur:
            toc.append(f'  <p class="toc-part">{esc(part_label(part))}</p>')
            cur = part
        label = title if part == "E" else f"{code} {title}"
        toc.append("  " + pp.toc_row(label, slug + "--top"))
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc += ["  </div>", "</section>"]

    out = [front, "\n".join(toc)]
    for part, slug, code, title, note, budget, body in items:
        crumb = mod.PART_CRUMB.get(part, part_label(part))
        if part != "E":
            crumb = f"{crumb}, {code}" if code != part else crumb
        full = f'<span class="full">Full notes p.&nbsp;{full_pages[slug]}</span>' if slug in full_pages else ""
        meta_line = f'<p class="sh__meta"><span>{esc(note)}</span>{full}</p>'
        out.append(f"""<article class="sheet" id="{slug}--top" data-budget="{budget}">{doc.marker(slug + "--top")}
  <header class="sh">
    <div class="sh__top"><p>{esc(crumb)}</p><p class="sh__rev">Revised<i></i><i></i><i></i></p></div>
    <h1>{esc(title)}</h1>
    {meta_line}
  </header>
  <div class="sn">
{ps.link_sheets(body, known)}  </div>
</article>""")

    text = " ".join(re.sub(r"<[^>]+>", " ", b) for *_, b in items)
    merged = {**psa.PRINT_ABBR, **ps.SHORT_ABBR, **build.ABBR}
    used = sorted(((k, v) for k, v in merged.items() if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", text)), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><b>{esc(k)}</b>: {esc(v)}</p>" for k, v in used]
    abbr += ["  </div>", "</section>"]
    out.append("\n".join(abbr))
    return head + "\n".join(out) + "\n</body>\n</html>\n", head + cover + "\n</body>\n</html>\n"


def budget_report(numbers, items):
    """Sheets that run over their page budget."""
    starts = [(numbers.get(f"{slug}--top"), slug, budget) for _, slug, _, _, _, budget, _ in items]
    ends = [s for s, _, _ in starts[1:]] + [numbers.get("abbr--top")]
    return [f"{slug} ({nxt - start} pages, budget {budget})"
            for (start, slug, budget), nxt in zip(starts, ends) if start and nxt and nxt - start > budget]


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in psub.SUBJECTS:
        sys.exit("usage: print_subject_short.py neuro|community [output.pdf]")
    cfg = psub.SUBJECTS[sys.argv[1]]
    mod = importlib.import_module(cfg["module"])
    build.ABBR = {**build.ABBR, **getattr(mod, cfg["abbr"])}
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else build.ROOT.parent / "PDF" / f"{cfg['file']} - short notes (print).pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    items = sheets(mod)
    if not items:
        sys.exit(f"no sheets found in {mod.SRC / 'short'}")
    full_pages = psa.full_notes_pages(cfg, mod)
    doc = pp.Doc()
    body_html, cover_html = build_html(doc, cfg, mod, items, full_pages)
    work = Path(tempfile.mkdtemp(prefix=f"{sys.argv[1]}-short-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    footer = f"{cfg['name']} short notes, MUHS IV BPTh"
    chrome = pp.Chrome()
    try:
        numbers, current = None, body_html
        for _ in range(4):
            body_file.write_text(current, encoding="utf-8")
            chrome.load(body_file.as_uri())
            chrome.pdf(work / "body.pdf", footer_text=footer)
            found = pp.page_numbers(work / "body.pdf", doc)
            if found == numbers:
                break
            numbers = found
            current, missing = pp.fill(body_html, numbers)
            if missing:
                print(f"warning: no page found for {len(missing)} anchors, e.g. {sorted(missing)[:5]}")
        else:
            print("warning: page numbers did not settle after 4 passes")
        chrome.load(cover_file.as_uri())
        chrome.pdf(work / "cover.pdf", footer=False)
    finally:
        chrome.close()
    subprocess.run(["pdfunite", str(work / "cover.pdf"), str(work / "body.pdf"), str(out_pdf)], check=True)
    over = budget_report(numbers, items)
    if over:
        print(f"over budget: {', '.join(over)}")
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((line for line in info.splitlines() if line.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, "
          f"{out_pdf.stat().st_size / 1e6:.1f} MB); {len(items)} of {len(mod.PAGES)} sheets")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
