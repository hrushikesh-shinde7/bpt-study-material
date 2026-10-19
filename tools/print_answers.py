#!/usr/bin/env python3
"""Build the printable A4 book of model answers to the 3- and 7-mark questions.

Answers live in src/cvr/answers/<slug>.html, one file per topic (same slugs
as the full pages). Each question is an <article class="qa"> with
data-marks (3 or 7) and data-asked (paper codes such as "S17-1b W17-1f";
Q1 is the 3-mark question, Q2 the 7-mark one). This script adds a cover, a
how-to page, contents, an index by paper and abbreviations, prints the
full-notes page for each topic, and can embed a diagram from the full notes
with <div class="figref" data-fig="ch6/burns#fb2t"></div> (the id of the
figure's title). Build the full notes first, then:

    python tools/print_answers.py [output.pdf]
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import print_pdf as pp  # noqa: E402
import print_short as ps  # noqa: E402

ANSWERS = build.SRC / "cvr" / "answers"
OUT_DEFAULT = build.ROOT.parent / "PDF" / "CVR Physiotherapy - 3 and 7 mark answers (print).pdf"
FOOTER = "CVR Physiotherapy model answers, MUHS IV BPTh"
PAPERS = ["S16", "W16", "S17", "W17", "S18", "W18", "S19", "W19", "S20", "W20",
          "S21", "W21", "S22", "W22", "S23", "S24", "W24", "S25", "W25", "S26"]

ANSWERS_CSS = """
.topic-head { column-span: all; break-after: avoid; display: flex; justify-content: space-between; align-items: baseline;
  gap: 4mm; margin: 4mm 0 2mm; padding-bottom: 1mm; border-bottom: 2px solid var(--ink); }
.topic-head:first-child { margin-top: 0; }
.topic-head h2 { font-family: var(--font-head); font-size: 13pt; line-height: 1.15; margin: 0; }
.topic-head .full { font-size: 7.8pt; color: var(--ink-2); white-space: nowrap; }
.book { columns: 2; column-gap: 5.5mm; }
.part-head { column-span: all; break-before: page; font-family: var(--font-head); font-size: 9pt; color: var(--ink-2); margin: 0 0 1mm; }
.part-head:first-child { break-before: auto; }
.qa { margin: 0 0 3.2mm; }
.qa > header { border-top: 1px solid var(--rule); padding-top: 1.3mm; break-after: avoid; break-inside: avoid; }
.qa .mk { display: inline-block; font-size: 7.2pt; font-weight: 700; padding: 0.2mm 1.4mm; border-radius: 2px; margin-right: 1.2mm; vertical-align: 0.2mm; }
.qa[data-marks="3"] .mk { background: var(--normal-tint); color: var(--normal); }
.qa[data-marks="7"] .mk { background: var(--action-tint); color: var(--action); }
.qa h3 { display: inline; font-size: 9.3pt; font-weight: 700; line-height: 1.25; }
.qa .asked { font-size: 7.4pt; color: var(--ink-2); margin: 0.5mm 0 1mm; }
.ans { break-before: avoid; }
.ans p { margin: 0 0 1mm; }
.ans ul, .ans ol { margin: 0 0 1mm; padding-left: 3.6mm; }
.ans li { margin: 0 0 0.4mm; break-inside: avoid; }
.ans li::marker { color: var(--ink-2); }
.ans h4 { font-size: 8.8pt; margin: 1.3mm 0 0.3mm; break-after: avoid; }
.ans .draw { border-left: 2px dashed var(--ink-2); padding: 0.3mm 0 0.3mm 2mm; color: var(--ink-2); font-size: 8.2pt; }
.ans .draw::before { content: "Draw: "; font-weight: 700; color: var(--ink); }
.ans .tip { font-size: 8.2pt; color: var(--ink-2); }
.figwrap { break-inside: avoid; margin: 1mm 0 1.6mm; }
.figwrap.wide { column-span: all; }
.figwrap .fig { margin: 0; break-inside: avoid; }
.figwrap .fig__head { padding: 0.3rem 0.6rem; }
.figwrap .fig__body { padding: 0.3rem; }
.figwrap .fig svg { max-width: 100%; max-height: 78mm; }
.figwrap.wide .fig svg { max-width: 118mm; max-height: 105mm; }
.figwrap .fig figcaption { font-size: 7.8pt; padding: 0 0.6rem 0.4rem; }
.figwrap .sketch-btn { display: none !important; }
.paper-index { break-before: page; }
.paper-index h1 { font-family: var(--font-head); font-size: 17pt; margin: 0 0 1.5mm; }
.paper-index > p { font-size: 8.6pt; margin: 0 0 3mm; }
.pi-cols { columns: 2; column-gap: 7mm; }
.pi-paper { break-inside: avoid; margin: 0 0 2.6mm; }
.pi-paper h3 { font-family: var(--font-head); font-size: 9.6pt; margin: 0 0 0.6mm; padding-bottom: 0.4mm; border-bottom: 1px solid var(--rule); }
.pi-row { display: flex; align-items: baseline; gap: 1.2mm; font-size: 7.7pt; line-height: 1.3; margin: 0.2mm 0; }
.pi-row .q { width: 6mm; flex: none; color: var(--ink-2); font-variant-numeric: tabular-nums; }
.pi-row .lead { flex: 1; border-bottom: 1px dotted #9aa6b2; transform: translateY(-0.7mm); min-width: 3mm; }
.pi-row .pg { min-width: 5mm; text-align: right; font-variant-numeric: tabular-nums; }
.front .marks-table { width: 100%; border-collapse: collapse; font-size: 9pt; margin: 2mm 0 3mm; }
.front .marks-table th, .front .marks-table td { text-align: left; vertical-align: top; padding: 1.2mm 2mm; border-bottom: 1px solid var(--rule); }
.front .marks-table thead th { border-bottom: 2px solid var(--ink); color: var(--ink-2); }
"""

ARTICLE_RE = re.compile(r'<article class="qa" id="([^"]+)" data-marks="(\d)" data-asked="([^"]+)">\s*<h3>(.*?)</h3>\s*<div class="ans">(.*?)</div>\s*</article>', re.S)


def esc(s):
    return html.escape(s, quote=True)


def code_label(code):
    paper, q = code.split("-")
    return f"{paper} ({q})"


def short_label(title):
    t = re.sub(r"<[^>]+>", "", title)
    t = re.split(r" \(|: ", t)[0]
    return t


def load_topics():
    """[(part, group, slug, title, [articles])] in book order; article = dict."""
    out = []
    for part, group, kind, slug, title in pp.page_list():
        f = ANSWERS / f"{slug}.html"
        if not f.exists():
            continue
        arts = []
        for aid, marks, asked, h3, body in ARTICLE_RE.findall(f.read_text(encoding="utf-8")):
            arts.append(dict(id=aid, marks=int(marks), asked=asked.split(), title=h3.strip(), body=body.strip(), slug=slug))
        arts.sort(key=lambda a: a["marks"])
        out.append((part, group, kind, slug, title, arts))
    return out


FIG_CACHE = {}


def figure_html(ref, n):
    """The figure whose title id is ref ("ch6/burns#fb2t"), with ids made unique."""
    page, _, fid = ref.partition("#")
    if page not in FIG_CACHE:
        FIG_CACHE[page] = (build.SRC / "cvr" / f"{page}.html").read_text(encoding="utf-8")
    src = FIG_CACHE[page]
    m = re.search(r'<figure class="fig" aria-labelledby="' + re.escape(fid) + r'">.*?</figure>', src, re.S)
    if not m:
        sys.exit(f"figure {ref} not found")
    fig = m.group(0)
    pre = f"af{n}-"
    fig = re.sub(r'\bid="([^"]+)"', lambda mm: f'id="{pre}{mm.group(1)}"', fig)
    fig = re.sub(r'url\(#([^)]+)\)', lambda mm: f"url(#{pre}{mm.group(1)})", fig)
    fig = re.sub(r'(xlink:href|href)="#([^"]+)"', lambda mm: f'{mm.group(1)}="#{pre}{mm.group(2)}"', fig)
    fig = re.sub(r'aria-labelledby="([^"]+)"', lambda mm: 'aria-labelledby="' + " ".join(pre + t for t in mm.group(1).split()) + '"', fig)
    fig = re.sub(r'<button[^>]*js-sketch[^>]*>.*?</button>', "", fig, flags=re.S)
    for old, new in pp.PRINT_WORDING:
        fig = fig.replace(old, new)
    return fig


def expand_figrefs(body, counter):
    def rep(m):
        counter[0] += 1
        wide = " wide" if 'data-wide' in m.group(0) else ""
        return f'<div class="figwrap{wide}">{figure_html(m.group(1), counter[0])}</div>'
    return re.sub(r'<div class="figref" data-fig="([^"]+)"[^>]*></div>', rep, body)


def link_answers(body, known_q, known_topics):
    def rep(m):
        target, text = m.group(1), m.group(2)
        if target in known_q:
            return f'<a class="xref">{text}</a>{pp.Doc.pref(known_q[target])}'
        if target in known_topics:
            return f'<a class="xref">{text}</a>{pp.Doc.pref(target + "--top")}'
        return text
    return re.sub(r'<a href="#([a-z0-9-]+)">(.*?)</a>', rep, body, flags=re.S)


def build_html(doc, topics, full_pages):
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>Cardio-Vascular and Respiratory Physiotherapy: 3- and 7-mark answers</title>
<link rel="stylesheet" href="{(build.ROOT / "assets" / "notes.css").as_uri()}">
<style>{ps.SHORT_CSS}{ANSWERS_CSS}</style>
</head>
<body class="print">
"""
    all_arts = [a for *_, arts in topics for a in arts]
    n3 = sum(1 for a in all_arts if a["marks"] == 3)
    n7 = len(all_arts) - n3
    known_q = {a["id"]: f'q-{a["slug"]}-{a["id"]}' for a in all_arts}
    known_topics = {t[3] for t in topics}

    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>Cardio-Vascular and Respiratory Physiotherapy</h1>
    <p class="cover__sub">Model answers to every 3-mark and 7-mark question asked from Summer 2016 to Summer 2026, written the way to write them in the exam.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Questions</dt><dd>All 240 short-answer slots of 20 papers: {n3} distinct 3-mark and {n7} distinct 7-mark questions after merging repeats</dd>
    <dt>Arranged</dt><dd>By topic, in the order of the full notes, with an index by paper at the end</dd>
    <dt>Content checked</dt><dd>{pp.DATE}</dd>
    <dt>Online version</dt><dd>{pp.SITE_URL}</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Every answer is drawn from the full notes, which list the sources for each fact.</p>
</section>"""

    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use the model answers</h1>
  <p>Every short-answer question from the 20 MUHS papers (Summer 2016 to Summer 2026) is here, once. When a question was repeated, the sessions are listed under it, so you can see which ones come back.</p>
  <ol>
    <li><b>Read the question, close the book, write your own answer</b> in the time allowed, then compare. Copying without recall does not stick.</li>
    <li><b>Learn the structure</b> as much as the facts: definition, points, table or diagram, precautions, one closing line.</li>
    <li><b>Practise whole papers.</b> The index at the back lists each paper's twelve short questions with the page of every answer: sit one paper in 100 minutes, then mark it.</li>
  </ol>
  <h2>What examiners look for</h2>
  <table class="marks-table">
    <thead><tr><th>Question</th><th>Length and time</th><th>Structure</th></tr></thead>
    <tbody>
      <tr><td><b>3 marks</b> (any 5 of 6)</td><td>Half a page; about 6 minutes</td><td>One-line definition, then 3–5 points, a small table or a labelled sketch; one line of physiotherapy relevance</td></tr>
      <tr><td><b>7 marks</b> (any 5 of 6)</td><td>One and a half to two pages; about 14 minutes</td><td>Definition or introduction; principle or classification; 6–8 headed points or a table with doses; a labelled diagram; precautions; one closing line</td></tr>
    </tbody>
  </table>
  <p>Write <b>doses with units</b> (repetitions, sets, times a day, minutes, RPE, % HRR) and <b>underline the keywords</b>. A <b>"Draw"</b> line in an answer tells you which diagram to draw; where the full notes have it, the diagram is printed beside the answer.</p>
  <p class="ask"><b>The paper:</b> 80 marks in 3 hours. Q1: any 5 of 6 at 3 marks (15). Q2: any 5 of 6 at 7 marks (35). Q3 and Q4: one 15-mark case each (30). About 2 minutes a mark. The 15-mark cases are covered in the full notes and short notes.</p>
</section>"""

    toc = ['<section class="toc-print">', "  <h1>Contents</h1>", '  <div class="toc-cols">']
    cur = None
    for part, group, kind, slug, title, arts in topics:
        label = "Part A: Chapter 6 conditions" if part == "A" else "Part B: Techniques, tests and other chapters"
        if label != cur:
            toc.append(f'  <p class="toc-part">{esc(label)}</p>')
            cur = label
        n = ", ".join(f"{c} × {m}" for m in (3, 7) if (c := sum(1 for a in arts if a["marks"] == m)))
        toc.append("  " + pp.toc_row(f"{title} ({n})", f"{slug}--top"))
    toc.append("  " + pp.toc_row("Index by paper", "paper-index--top"))
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc += ["  </div>", "</section>"]

    body = ['<section class="sheet" id="answers--top">' + doc.marker("answers--top"), '<div class="book">']
    counter = [0]
    cur_part = None
    for part, group, kind, slug, title, arts in topics:
        part_label = "Part A: Chapter 6 conditions" if part == "A" else "Part B: Techniques, tests and other chapters"
        if part_label != cur_part:
            body.append(f'<p class="part-head">{esc(part_label)}</p>')
            cur_part = part_label
        full = f'<span class="full">Full notes p.&nbsp;{full_pages[slug]}</span>' if slug in full_pages else ""
        body.append(f'<div class="topic-head" id="{slug}--top">{doc.marker(slug + "--top")}<h2>{esc(title)}</h2>{full}</div>')
        for a in arts:
            anchor = known_q[a["id"]]
            asked = ", ".join(code_label(c) for c in a["asked"])
            times = len(a["asked"])
            times_txt = f" (asked {times} times)" if times > 1 else ""
            ans = expand_figrefs(a["body"], counter)
            ans = link_answers(ans, known_q, known_topics)
            body.append(f"""<article class="qa" id="{anchor}" data-marks="{a['marks']}">{doc.marker(anchor)}
  <header><span class="mk">{a['marks']} marks</span><h3>{a['title']}</h3><p class="asked">Asked: {asked}{times_txt}</p></header>
  <div class="ans">{ans}</div>
</article>""")
    body += ["</div>", "</section>"]

    by_code = {}
    for a in all_arts:
        for c in a["asked"]:
            by_code[c] = a
    names = {"S": "Summer", "W": "Winter"}
    pi = [f'<section class="paper-index" id="paper-index--top">{doc.marker("paper-index--top")}', "  <h1>Index by paper</h1>",
          "  <p>Each paper's twelve short questions (Q1 at 3 marks, Q2 at 7 marks) with the page of the model answer. Sit a paper in 100 minutes (five of each), then check.</p>",
          '  <div class="pi-cols">']
    for p in PAPERS:
        pi.append(f'  <div class="pi-paper"><h3>{names[p[0]]} 20{p[1:]}</h3>')
        for q in ("1", "2"):
            for letter in "abcdef":
                code = f"{p}-{q}{letter}"
                a = by_code.get(code)
                if not a:
                    continue
                pi.append(f'    <div class="pi-row"><span class="q">{q}{letter}</span><span>{esc(short_label(a["title"]))}</span>'
                          f'<span class="lead"></span><span class="pg">{pp.pnum(known_q[a["id"]])}</span></div>')
        pi.append("  </div>")
    pi += ["  </div>", "</section>"]

    items_ab = sorted({**ps.SHORT_ABBR, **build.ABBR}.items(), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><b>{esc(k)}</b>: {esc(v)}</p>" for k, v in items_ab]
    abbr += ["  </div>", "</section>"]

    page = head + "\n".join([front, "\n".join(toc), "\n".join(body), "\n".join(pi), "\n".join(abbr)]) + "\n</body>\n</html>\n"
    return page, head + cover + "\n</body>\n</html>\n"


def main():
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    topics = load_topics()
    arts = [a for *_, al in topics for a in al]
    empty = [a["id"] for a in arts if not re.sub(r"\s", "", a["body"])]
    codes = [c for a in arts for c in a["asked"]]
    if len(codes) != len(set(codes)):
        sys.exit("a paper code is used by more than one answer")
    full_pages = ps.full_notes_pages()
    doc = pp.Doc()
    body_html, cover_html = build_html(doc, topics, full_pages)
    work = Path(tempfile.mkdtemp(prefix="cvr-answers-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    body_file.write_text(body_html, encoding="utf-8")
    chrome = pp.Chrome()
    try:
        # render until the page numbers written into the text stop moving the text itself
        numbers, current = None, body_html
        for _ in range(4):
            body_file.write_text(current, encoding="utf-8")
            chrome.load(body_file.as_uri())
            chrome.pdf(work / "body.pdf", footer_text=FOOTER)
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
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((l for l in info.splitlines() if l.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, {out_pdf.stat().st_size / 1e6:.1f} MB); "
          f"{len(arts)} questions in {len(topics)} topics, {len(set(codes))} paper slots; {len(empty)} answers still empty")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
