#!/usr/bin/env python3
"""Build a printable A4 PDF of the syllabus-order version (cvr-syllabus/).

Uses the same assembly as tools/build_syllabus.py and lays it out as a book:
a cover, a how-to page, contents, an opener page for each syllabus chapter
listing its items with page numbers, every syllabus page, and the
abbreviations. Headless Chrome renders it until the page numbers settle.

Needs Google Chrome, poppler (pdftotext, pdfunite) and the Python package
websocket-client:

    python tools/print_syllabus.py [output.pdf]
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import build_syllabus as bs  # noqa: E402
import print_pdf as pp  # noqa: E402

OUT_DEFAULT = build.ROOT.parent / "PDF" / "CVR Physiotherapy - syllabus order (print).pdf"
FOOTER = "CVR Physiotherapy in syllabus order, MUHS IV BPTh"
SITE_URL = pp.SITE_URL + "cvr-syllabus/"
LINK_RE = re.compile(r'<a href="([^"]*)">(.*?)</a>', re.S)

EXTRA_CSS = """
.ptopic > h1 .h1code { vertical-align: 0.12em; }
.toc-row .code { min-width: 13mm; font-weight: 700; color: var(--normal); font-variant-numeric: tabular-nums; }
.toc-row.sub { padding-left: 13mm; }
.toc-row.sub .code { min-width: 9mm; }
.toc-row.label .lead, .toc-row.label .pg { visibility: hidden; }
.part-page .hours { font-size: 10pt; color: var(--ink-2); margin: 0 0 2mm; }
.part-toc .toc-row { font-size: 9.6pt; margin: 1mm 0; }
"""


def esc(s):
    return pp.esc(s)


def row(code, title, anchor, cls=""):
    pg = pp.pnum(anchor) if anchor else ""
    label = " label" if not anchor else ""
    return (f'<div class="toc-row{cls}{label}"><span class="code">{esc(code)}</span><span>{esc(title)}</span>'
            f'<span class="lead"></span><span class="pg">{pg}</span></div>')


def anchor_of(target):
    """A syllabus target ("page" or "page#id") as an anchor in the print document."""
    page, _, frag = target.partition("#")
    return f"{page}--{frag}" if frag else f"{page}--top"


def transform(slug, body, slugs):
    """Make one page's notes printable: open answers, unique ids, links as page references."""
    body = re.sub(r'\s*<div class="pagefoot">.*?</div>', "", body, flags=re.S)
    body = body.replace("<details ", "<details open ").replace("<details>", "<details open>")
    for old, new in pp.PRINT_WORDING:
        body = body.replace(old, new)
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{slug}--{m.group(1)}"', body)
    body = re.sub(r'url\(#([^)]+)\)', lambda m: f"url(#{slug}--{m.group(1)})", body)
    body = re.sub(r'aria-(labelledby|describedby)="([^"]+)"',
                  lambda m: f'aria-{m.group(1)}="' + " ".join(f"{slug}--{t}" for t in m.group(2).split()) + '"', body)

    def link(m):
        href, text = m.group(1), m.group(2)
        if href.startswith(("http://", "https://", "mailto:")):
            return f"<a>{text}</a>"
        path, _, frag = href.partition("#")
        target = slug if path == "" else path[:-5] if path.endswith(".html") and path[:-5] in slugs else None
        if target is None:
            return text
        anchor = f"{target}--{frag}" if frag else f"{target}--top"
        return f'<a class="xref" href="#{anchor}">{text}</a>{pp.Doc.pref(anchor)}'
    return LINK_RE.sub(link, body)


def chapter_rows(items, cls=""):
    """Rows for a chapter's syllabus items, with sub-items indented."""
    out = []
    for code, wording, target, subs in items:
        if subs:
            out.append(row(code, wording, anchor_of(target) if isinstance(target, str) else None, cls))
            out += [row(c, w, anchor_of(t), " sub") for c, w, t in subs]
        elif isinstance(target, list):
            out.append(row(code, wording, None, cls))
            out += [row("", next(p.h1 for p in bs.PAGES if p.slug == t), anchor_of(t), " sub") for t in target]
        else:
            out.append(row(code, wording, anchor_of(target), cls))
    return out


def build_html(doc):
    asm = bs.Assembler()
    for page in bs.PAGES:
        asm.assemble(page)
    slugs = {p.slug for p in bs.PAGES}
    css = "".join(f'<link rel="stylesheet" href="{(build.ROOT / "assets" / name).as_uri()}">\n' for name in ("notes.css", "syllabus.css"))
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>Cardio-Vascular and Respiratory Physiotherapy in syllabus order</title>
{css}<style>{pp.PRINT_CSS}{EXTRA_CSS}</style>
</head>
<body class="print">
"""
    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>Cardio-Vascular and Respiratory Physiotherapy</h1>
    <p class="cover__sub">Complete exam notes in syllabus order: Chapters 1 to 11, the practical list and exam skills.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Built from</dt><dd>20 MUHS question papers, Summer 2016 to Summer 2026 (code 51413)</dd>
    <dt>Arrangement</dt><dd>The order of the MUHS syllabus, so the notes follow the order your college teaches</dd>
    <dt>Contents</dt><dd>{len(bs.PAGES)} syllabus pages with past questions, answer skeletons and self-tests</dd>
    <dt>Content checked</dt><dd>{pp.DATE}</dd>
    <dt>Online version</dt><dd>{SITE_URL}</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Written in original words from current textbooks and dated guidelines; each page lists its sources.</p>
</section>"""

    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use these notes</h1>
  <ol>
    <li><strong>Follow your classes.</strong> The chapters are in the order of the MUHS syllabus. Each chapter opens with its syllabus items and their pages.</li>
    <li><strong>Read a topic once</strong>, slowly, including the "Why?" boxes.</li>
    <li><strong>Close it and recall.</strong> Write the keywords and draw the diagrams on paper from memory, then compare.</li>
    <li><strong>Test yourself</strong> with the questions at the end of each topic. Cover the answer before you look.</li>
    <li><strong>Come back</strong> on day 1, day 7 and day 21. Testing yourself again beats re-reading.</li>
  </ol>
  <div class="note note--exam">
    <span class="note__label">What the real paper looks like (20 papers, 2016–2026)</span>
    <p>80 marks in 3 hours. <strong>No MCQs</strong>, even though the syllabus printed a scheme with them.</p>
    <ul>
      <li>Short answers: any 5 of 6 at <strong>3 marks</strong>, and any 5 of 6 at <strong>7 marks</strong>.</li>
      <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. Every option is a patient case, and almost all ask for ICF, a functional diagnosis or impairments.</li>
    </ul>
    <p>Since 2023, ventilated ICU patients appear as long cases and an ICU short question is in every paper, so give Chapter 9 the same time as the Tier 1 conditions in Chapter 6.</p>
  </div>
  <h3>How this book is arranged</h3>
  <ul>
    <li><strong>Chapters 1 to 11</strong> follow the MUHS 2012 syllabus. Each page title starts with its syllabus code, for example 6(c)(iv) for bronchiectasis.</li>
    <li>Where several small syllabus items share a page, each has its own section, numbered with the syllabus numeral (i, ii, iii).</li>
    <li><strong>Practical skills</strong>: the syllabus practical list, with handling skills and equipment.</li>
    <li><strong>Exam skills</strong>: answer writing for the theory paper, and the practical exam.</li>
  </ul>
  <p>Each topic opens with its syllabus heading, priority, the sessions it was asked in (LAQ = 15-mark long answer, 7m and 3m = short answers; S = Summer, W = Winter, for example S24 = Summer 2024), and the guidelines it was checked against. Page references such as (p. 123) point to related pages. Abbreviations are listed at the end.</p>
</section>"""

    toc = ['<section class="toc-print">', "  <h1>Contents</h1>", "  " + pp.toc_row("How to use these notes", "front--top")]
    articles = []
    chapters = {c[0]: c for c in bs.CHAPTERS + bs.EXTRA_PARTS}
    cur_ch, cur_group = None, None
    for page in bs.PAGES:
        if page.chapter != cur_ch:
            key, title, hours, items = chapters[page.chapter]
            label = f"Chapter {key}: {title}" if key.isdigit() else title
            toc.append(f'  <p class="toc-part">{esc(label)}</p>')
            openers_html = (f'<section class="part-page" id="ch{key}--top">{doc.marker(f"ch{key}--top")}'
                            f'<p class="part-letter">{"Chapter " + key if key.isdigit() else "Part"}</p>'
                            f'<h1>{esc(title)}</h1><p class="hours">{esc(hours)}</p>'
                            f'<div class="part-toc">{"".join(chapter_rows(items))}</div></section>')
            articles.append(openers_html)
            cur_ch, cur_group = page.chapter, None
        if page.crumb and page.crumb != cur_group:
            toc.append(f'  <p class="toc-group">{esc(page.crumb)}</p>')
            cur_group = page.crumb
        toc.append("  " + row(page.code if page.chapter.isdigit() else "", page.h1, f"{page.slug}--top"))

        meta, body = bs.page_body(page, asm)
        body = transform(page.slug, body, slugs)
        crumb = " › ".join([bs.crumb_for(page.chapter)] + ([page.crumb] if page.crumb else []))
        header = transform(page.slug, f"""<p class="lede">{meta['lede']}</p>
  <table class="pmeta"><tbody>
    <tr><th scope="row">Syllabus</th><td>{meta['syllabus']}</td></tr>
    <tr><th scope="row">Priority</th><td>{meta['priority']}</td></tr>
    <tr><th scope="row">Asked as</th><td>{meta['asked']}</td></tr>
    <tr><th scope="row">Usual split</th><td>{meta['split']}</td></tr>
    <tr><th scope="row">Checked against</th><td>{meta['checked']} Content checked {meta['date']}.</td></tr>
  </tbody></table>""", slugs)
        articles.append(f"""<article class="ptopic" id="{page.slug}--top">{doc.marker(page.slug + "--top")}
  <p class="ptopic__crumb">{esc(crumb)}</p>
  <h1><span class="h1code">{esc(page.code)}</span>{esc(page.h1)}</h1>
  {header}
{body}
</article>""")
    toc.append('  <p class="toc-part">Appendix</p>')
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc.append("</section>")

    items = sorted(build.ABBR.items(), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><strong>{esc(k)}</strong>: {esc(v)}</p>" for k, v in items]
    abbr += ["  </div>", "</section>"]

    parts = [front, "\n".join(toc)] + articles + ["\n".join(abbr)]
    whole = "\n".join(parts)
    targets = set(re.findall(r'href="#([^"]+)"', whole)) | set(re.findall(r'data-ref="([^"]+)"', whole))
    parts = [pp.add_markers(doc, p, targets) if p.startswith("<article") else p for p in parts]
    missing = sorted(t for t in targets if f'id="{t}"' not in whole)
    body_html = head + "\n".join(parts) + "\n</body>\n</html>\n"
    cover_html = head + cover + "\n</body>\n</html>\n"
    return body_html, cover_html, missing


def main():
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = pp.Doc()
    body_html, cover_html, missing = build_html(doc)
    if missing:
        print(f"warning: {len(missing)} link targets have no element, e.g. {missing[:5]}")
    work = Path(tempfile.mkdtemp(prefix="cvr-syllabus-print-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    chrome = pp.Chrome()
    try:
        numbers, current = None, body_html
        for _ in range(4):
            body_file.write_text(current, encoding="utf-8")
            chrome.load(body_file.as_uri())
            chrome.pdf(work / "body.pdf", footer_text=FOOTER)
            found = pp.page_numbers(work / "body.pdf", doc)
            if found == numbers:
                break
            numbers = found
            current, unfound = pp.fill(body_html, numbers)
        else:
            print("warning: page numbers did not settle after 4 passes")
        if unfound:
            print(f"warning: no page found for {len(unfound)} anchors, e.g. {sorted(unfound)[:5]}")
        chrome.load(cover_file.as_uri())
        chrome.pdf(work / "cover.pdf", footer=False)
    finally:
        chrome.close()
    subprocess.run(["pdfunite", str(work / "cover.pdf"), str(work / "body.pdf"), str(out_pdf)], check=True)
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((line for line in info.splitlines() if line.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, "
          f"{out_pdf.stat().st_size / 1e6:.1f} MB); {len(bs.PAGES)} pages in {len(bs.CHAPTERS)} chapters plus practical and exam skills; "
          f"markers found {len(numbers)} of {len(doc.markers)}")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
