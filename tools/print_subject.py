#!/usr/bin/env python3
"""Build a printable A4 PDF of the Neuro or Community notes, in syllabus order.

Lays the subject out as a book: a cover, a how-to page, contents, an opener
page for each syllabus part listing its pages with page numbers, every page,
and the abbreviations used. Headless Chrome renders it until the page numbers
settle. Uses the same print styles and page-number machinery as
tools/print_pdf.py.

Needs Google Chrome, poppler (pdftotext, pdfunite) and the Python package
websocket-client:

    python tools/print_subject.py neuro [output.pdf]
    python tools/print_subject.py community [output.pdf]
"""
import importlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import print_pdf as pp  # noqa: E402

LINK_RE = re.compile(r'<a href="([^"]*)">(.*?)</a>', re.S)

SUBJECTS = {
    "neuro": dict(
        module="build_neuro", abbr="NEURO_ABBR", folder="neuro", code="51412",
        name="Neuro Physiotherapy", file="Neuro Physiotherapy",
        sub="Complete exam notes in syllabus order: Chapters 1 to 4, assessment, adult and paediatric conditions, the treatment programme and exam skills.",
        practical="Practical: long case 45, short case 20, spots 10, journal 5.",
        cases="Almost every long case is a patient with a neurological condition; most ask for ICF, a functional diagnosis or impairments, goals and management.",
    ),
    "community": dict(
        module="build_community", abbr="COMMUNITY_ABBR", folder="community", code="51414",
        name="Community Physiotherapy", file="Community Physiotherapy",
        sub="Complete exam notes in syllabus order: health promotion, women's health, geriatrics, rehabilitation, disaster management, industrial health, the project synopsis and exam skills.",
        practical="Practical: long case 50, project synopsis 25, journal 5.",
        cases="Most long cases are a person in a community setting (a worker in pain, a pregnant or postnatal woman, an older person, a person with disability) or a planning question; answers need ICF, goals, treatment with doses, and ergonomic, home or community measures.",
    ),
}

EXTRA_CSS = """
.ptopic > h1 .h1code { vertical-align: 0.12em; }
.toc-row .code { min-width: 15mm; font-weight: 700; color: var(--normal); font-variant-numeric: tabular-nums; }
.part-page .hours { font-size: 10pt; color: var(--ink-2); margin: 0 0 2mm; }
.part-toc .toc-row { font-size: 9.6pt; margin: 1mm 0; }
"""


def esc(s):
    return pp.esc(s)


def row(code, title, anchor):
    return (f'<div class="toc-row"><span class="code">{esc(code)}</span><span>{esc(title)}</span>'
            f'<span class="lead"></span><span class="pg">{pp.pnum(anchor)}</span></div>')


def transform(slug, body, slugs):
    """Make one page printable: open answers, unique ids, links as page references."""
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


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))


def build_html(doc, cfg, mod):
    build.ABBR = {**build.ABBR, **getattr(mod, cfg["abbr"])}
    pages = [p for p in mod.PAGES if (mod.SRC / f"{p[0]}.html").exists()]
    if len(pages) < len(mod.PAGES):
        print(f"warning: only {len(pages)} of {len(mod.PAGES)} pages are written")
    slugs = {p[0] for p in pages}
    css = "".join(f'<link rel="stylesheet" href="{(build.ROOT / "assets" / name).as_uri()}">\n' for name in ("notes.css", "syllabus.css"))
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>{esc(cfg['name'])} in syllabus order</title>
{css}<style>{pp.PRINT_CSS}{EXTRA_CSS}</style>
</head>
<body class="print">
"""
    dates = []
    articles, toc, all_text = [], ['<section class="toc-print">', "  <h1>Contents</h1>", "  " + pp.toc_row("How to use these notes", "front--top")], []
    parts = {p[0]: p for p in mod.PARTS}
    cur_part = None
    for slug, code, title, part, _ in pages:
        if part != cur_part:
            key, ptitle, hours = parts[part]
            label = f"Part {key}: {ptitle}" if key != "E" else ptitle
            toc.append(f'  <p class="toc-part">{esc(label)}</p>')
            in_part = [(s, c, t) for s, c, t, p, _ in pages if p == part]
            rows = "".join(row(c, t, f"{s}--top") for s, c, t in in_part)
            if len(in_part) >= 3:  # parts with one or two pages need no divider page
                articles.append(f'<section class="part-page" id="part{key}--top">{doc.marker(f"part{key}--top")}'
                                f'<p class="part-letter">{"Part " + esc(key) if key != "E" else "Exam skills"}</p>'
                                f'<h1>{esc(ptitle)}</h1><p class="hours">{esc(hours)}</p>'
                                f'<div class="part-toc">{rows}</div></section>')
            cur_part = part
        meta, body = build.parse_source(mod.SRC / f"{slug}.html")
        dates.append(meta["date"])
        body = build.add_abbr(body)
        all_text.append(plain(body) + " " + plain(" ".join(meta.values())))
        toc.append("  " + row(code if code != "Exam" else "", meta["h1"], f"{slug}--top"))
        crumb = " › ".join([mod.PART_CRUMB[part], meta["crumb"]])
        header = transform(slug, f"""<p class="lede">{meta['lede']}</p>
  <table class="pmeta"><tbody>
    <tr><th scope="row">Syllabus</th><td>{meta['syllabus']}</td></tr>
    <tr><th scope="row">Priority</th><td>{meta['priority']}</td></tr>
    <tr><th scope="row">Asked as</th><td>{meta['asked']}</td></tr>
    <tr><th scope="row">Usual split</th><td>{meta['split']}</td></tr>
    <tr><th scope="row">Checked against</th><td>{meta['checked']} Content checked {meta['date']}.</td></tr>
  </tbody></table>""", slugs)
        articles.append(f"""<article class="ptopic" id="{slug}--top">{doc.marker(slug + "--top")}
  <p class="ptopic__crumb">{esc(crumb)}</p>
  <h1><span class="h1code">{esc(code)}</span>{meta['h1']}</h1>
  {header}
{transform(slug, body, slugs)}
</article>""")
    toc.append('  <p class="toc-part">Appendix</p>')
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc.append("</section>")

    text = " ".join(all_text)
    used = sorted(((k, v) for k, v in build.ABBR.items() if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", text)),
                  key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><strong>{esc(k)}</strong>: {esc(v)}</p>" for k, v in used]
    abbr += ["  </div>", "</section>"]

    latest = max(dates, key=lambda d: (int(d.split()[2]), ["January", "February", "March", "April", "May", "June", "July", "August",
                                                          "September", "October", "November", "December"].index(d.split()[1]), int(d.split()[0])))
    site_url = pp.SITE_URL + cfg["folder"] + "/"
    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>{esc(cfg['name'])}</h1>
    <p class="cover__sub">{esc(cfg['sub'])}</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Built from</dt><dd>20 MUHS question papers, Summer 2016 to Summer 2026 (code {cfg['code']})</dd>
    <dt>Arrangement</dt><dd>The order of the MUHS syllabus, so the notes follow the order your college teaches</dd>
    <dt>Contents</dt><dd>{len(pages)} pages with past questions, worked long cases, answer skeletons and self-tests</dd>
    <dt>Content checked</dt><dd>{esc(latest)}</dd>
    <dt>Online version</dt><dd>{site_url}</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Written in original words from current textbooks and dated guidelines; each page lists its sources.</p>
</section>"""
    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use these notes</h1>
  <ol>
    <li><strong>Follow your classes.</strong> The parts are in the order of the MUHS syllabus. Each part opens with its pages and their page numbers.</li>
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
      <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. {esc(cfg['cases'])}</li>
    </ul>
    <p>{esc(cfg['practical'])} See the exam skills pages at the end.</p>
  </div>
  <h3>How each topic is laid out</h3>
  <p>Each topic opens with its syllabus heading, priority, the sessions it was asked in (LAQ = 15-mark long answer, 7m and 3m = short answers; S = Summer, W = Winter, for example S24 = Summer 2024), the usual mark split, and the guidelines it was checked against. Page references such as (p. 123) point to related pages in this book. Abbreviations are listed at the end.</p>
</section>"""

    body_parts = [front, "\n".join(toc)] + articles + ["\n".join(abbr)]
    whole = "\n".join(body_parts)
    targets = set(re.findall(r'href="#([^"]+)"', whole)) | set(re.findall(r'data-ref="([^"]+)"', whole))
    body_parts = [pp.add_markers(doc, p, targets) if p.startswith("<article") else p for p in body_parts]
    missing = sorted(t for t in targets if f'id="{t}"' not in whole)
    return head + "\n".join(body_parts) + "\n</body>\n</html>\n", head + cover + "\n</body>\n</html>\n", missing, len(pages)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SUBJECTS:
        sys.exit("usage: print_subject.py neuro|community [output.pdf]")
    cfg = SUBJECTS[sys.argv[1]]
    mod = importlib.import_module(cfg["module"])
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else build.ROOT.parent / "PDF" / f"{cfg['file']} - complete notes (print).pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    footer = f"{cfg['name']} in syllabus order, MUHS IV BPTh"
    doc = pp.Doc()
    body_html, cover_html, missing, n_pages = build_html(doc, cfg, mod)
    if missing:
        print(f"warning: {len(missing)} link targets have no element, e.g. {missing[:5]}")
    work = Path(tempfile.mkdtemp(prefix=f"{sys.argv[1]}-print-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    chrome = pp.Chrome()
    unfound = set()
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
          f"{out_pdf.stat().st_size / 1e6:.1f} MB); {n_pages} topic pages; markers found {len(numbers)} of {len(doc.markers)}")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
