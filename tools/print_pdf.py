#!/usr/bin/env python3
"""Build one printable A4 PDF of the whole CVR site.

Assembles every page (Chapter 6 topics, technique cards, other chapters,
exam skills) into one print document with a cover, contents, syllabus map
and abbreviations, then renders it twice with headless Chrome so that the
contents and cross-references carry real page numbers.

Needs Google Chrome, poppler (pdftotext, pdfunite) and the Python package
websocket-client. Run with a Python that has websocket-client:

    python tools/print_pdf.py [output.pdf]
"""
import base64
import html
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402

import websocket  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = build.ROOT
OUT_DEFAULT = ROOT.parent / "PDF" / "CVR Physiotherapy - complete notes (print).pdf"
SITE_URL = "https://hrushikesh-shinde7.github.io/bpt-study-material/"
DATE = "19 October 2026"

TIER_TITLES = {
    1: "Tier 1: full notes, asked almost every year",
    2: "Tier 2: asked sometimes",
    3: "Tier 3: short notes, rarely or never asked on their own",
}
PARTS = [
    ("A", "Chapter 6: Physiotherapy management", "Conditions, in the order they score in the real papers."),
    ("B", "Technique cards", "Skills, devices, tests and scales that the short answers ask about."),
    ("C", "Other syllabus chapters", "Rehabilitation programmes, the revision chapter and basic life support."),
    ("D", "Exam skills", "Answer writing with ICF and goals, and the practical exam."),
]
SECTION_PART = {"cards": "B", "chapters": "C", "exam": "D"}
# screen wording that reads wrongly on paper
PRINT_WORDING = [
    ("Answer on paper first, then open the answer.", "Cover each answer and write yours on paper first, then check."),
    ("Then scroll up and compare", "Then look back and compare"),
    ("draw the sketch version", "draw a quick sketch"),
    ("for this site", "for these notes"),
]
SYLLABUS_MAP = [
    ("1", "Review of applied anatomy, physiology and pharmacology", ["respiratory-basics", "cardiac-basics", "drugs"]),
    ("2", "Investigations and exercise testing", ["investigations", "abg", "breathing-patterns", "exercise-testing"]),
    ("3", "Exercise physiology", ["exercise-physiology", "bed-rest"]),
    ("4", "Physiotherapy skills", ["airway-clearance", "acbt", "postural-drainage", "airway-devices", "positioning",
                                    "dyspnoea", "aerosol-humidification", "breathing-exercises", "npf-pnf",
                                    "electrotherapy-exercise", "respiratory-muscle-training", "yoga", "oxygen-therapy"]),
    ("5", "Application of the ICF model", ["answer-writing"]),
    ("6", "Physiotherapy management (23 topics)", ["@part-A"]),
    ("7", "Cardiac rehabilitation", ["cardiac-rehab"]),
    ("8", "Pulmonary rehabilitation", ["pulmonary-rehab"]),
    ("9", "ICU evaluation and management", ["icu-physiotherapy", "mechanical-ventilation", "suctioning",
                                           "icu-neurological", "icu-medical"]),
    ("10", "Functional scales", ["scales"]),
    ("11", "Basic life support", ["bls"]),
    ("Practical", "Practical examination and skills", ["practical-exam", "handling-skills"]),
]

PRINT_CSS = """
@page { size: A4; }
html { font-size: 9.4pt; }
body.print { background: #fff; line-height: 1.42; margin: 0; }
.pm { font-size: 1px; line-height: 0; color: #fff; }
.pagebreak, article.ptopic, .part-page, .front, .toc-print, .smap, .abbr-list { break-before: page; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; padding: 20mm 6mm 0; }
.cover__kicker { font-size: 11pt; color: var(--ink-2); margin: 0; }
.cover h1 { font-size: 30pt; line-height: 1.12; margin: 6mm 0 4mm; }
.cover__sub { font-size: 13pt; margin: 0 0 10mm; max-width: 140mm; }
.cover__trace { width: 100%; height: 14mm; }
.cover__trace path { fill: none; stroke: var(--ecg-trace); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.cover dl { display: grid; grid-template-columns: 38mm 1fr; gap: 2mm 6mm; font-size: 10pt; margin: 0; }
.cover dt { font-weight: 700; color: var(--ink-2); }
.cover dd { margin: 0; }
.cover__foot { font-size: 8.5pt; color: var(--ink-2); border-top: 1px solid var(--rule); padding-top: 3mm; }
h1 { font-size: 18pt; }
h2 { font-size: 13.5pt; break-after: avoid; }
h3 { font-size: 11.2pt; margin-top: 1rem; break-after: avoid; }
h4 { break-after: avoid; }
p, li { orphans: 2; widows: 2; }
a { color: inherit; text-decoration: none; }
a.xref { text-decoration: underline; text-decoration-color: #9aa6b2; text-underline-offset: 0.15em; }
.pref { font-variant-numeric: tabular-nums; color: var(--ink-2); font-size: 0.92em; white-space: nowrap; }
abbr[title] { text-decoration: none; }
.part-page { padding-top: 24mm; }
.part-page .part-letter { font-family: var(--font-head); font-size: 14pt; color: var(--ink-2); margin: 0; }
.part-page h1 { font-size: 26pt; margin: 2mm 0 4mm; }
.part-page > p { font-size: 11pt; max-width: 130mm; }
.part-toc { margin-top: 10mm; padding-top: 3mm; border-top: 2px solid var(--ink); }
.part-toc .toc-group:first-child { margin-top: 0; }
.ptopic__crumb { font-size: 8.8pt; color: var(--ink-2); margin: 0 0 1.5mm; }
.ptopic > h1 { margin: 0 0 2mm; }
.ptopic .lede { font-size: 10.2pt; margin: 2mm 0 3mm; padding: 1.5mm 3mm; }
.pmeta { width: 100%; border-collapse: collapse; font-size: 8.6pt; margin: 0 0 2mm; }
.pmeta th { width: 27mm; text-align: left; vertical-align: top; color: var(--ink-2); padding: 0.8mm 2mm 0.8mm 0; }
.pmeta td { vertical-align: top; padding: 0.8mm 0; border-bottom: 1px dashed var(--rule); }
.pmeta .chip { font-size: 7.8pt; padding: 0 1.2mm; margin: 0 0.6mm 0.6mm 0; }
.sec { margin-top: 1.25rem; }
.sec h2 { padding-bottom: 1mm; border-bottom: 1px solid var(--rule); }
.tbl { font-size: 8.8pt; margin: 0.6rem 0 0.9rem; }
.tbl th, .tbl td { padding: 0.32rem 0.45rem; }
.tbl tr { break-inside: avoid; }
.tbl thead { display: table-header-group; }
.fig { break-inside: avoid; margin: 0.8rem 0; }
.fig__head { padding: 0.3rem 0.7rem; }
.fig__body { padding: 0.4rem; }
.fig svg { max-width: 108mm; max-height: 122mm; }
.fig figcaption { font-size: 8.6pt; padding: 0 0.7rem 0.45rem; }
.sketch-btn { display: none !important; }
.note, .hook, .cvc, .recall { break-inside: avoid; margin: 0.8rem 0; }
.cvc__grid { grid-template-columns: 1fr 1fr 1fr; }
.cvc__cell { border-bottom: 0; border-right: 1px solid var(--rule); }
.cvc__cell:last-child { border-right: 0; }
details > summary { list-style: none; }
details > summary::-webkit-details-marker { display: none; }
details.why { break-inside: avoid; }
details.why > summary { font-weight: 700; }
details.q { break-inside: avoid; }
details.q > summary::after { content: "" !important; }
details.q .a { border-left: 3px solid var(--action-fill); padding-left: 2.5mm; margin-top: 1mm; }
details.q .a::before { content: "Answer"; display: block; font-size: 7.8pt; font-weight: 700; color: var(--action); letter-spacing: 0.02em; }
.selftest { break-inside: auto; border: 0; border-top: 2px solid var(--ink); border-bottom: 2px solid var(--ink); border-radius: 0; padding: 2.5mm 0 1mm; }
.sources { font-size: 7.8pt; line-height: 1.32; }
.sources h2 { font-size: 10.5pt; }
.sources h2 .n { display: none; }
.sources h2, .sources h2 + p { break-after: avoid; }
.sources > p { margin: 0.5mm 0 0; }
.sources ol { columns: 2; column-gap: 6mm; padding-left: 0; margin: 1.5mm 0 0; }
.sources li { margin: 0 0 0.8mm 5.2mm; break-inside: avoid; }
.toc-print h1, .smap h1, .front h1, .abbr-list h1 { font-size: 18pt; margin-bottom: 3mm; }
.toc-part { font-family: var(--font-head); font-size: 12pt; font-weight: 700; margin: 4mm 0 1mm; }
.toc-group { font-size: 9pt; font-weight: 700; color: var(--ink-2); margin: 2.2mm 0 0.6mm; }
.toc-row { display: flex; align-items: baseline; gap: 1.5mm; font-size: 9.4pt; margin: 0.5mm 0; break-inside: avoid; }
.toc-row .lead { flex: 1; border-bottom: 1px dotted #9aa6b2; transform: translateY(-1mm); min-width: 6mm; }
.toc-row .pg { font-variant-numeric: tabular-nums; min-width: 7mm; text-align: right; }
.smap table { width: 100%; border-collapse: collapse; font-size: 9.2pt; }
.smap th, .smap td { text-align: left; vertical-align: top; padding: 1.4mm 2mm; border-bottom: 1px solid var(--rule); }
.smap thead th { border-bottom: 2px solid var(--ink); color: var(--ink-2); font-size: 8.6pt; }
.abbr-cols { columns: 2; column-gap: 8mm; font-size: 8.8pt; }
.abbr-cols p { margin: 0 0 1mm; break-inside: avoid; }
.front .note { break-inside: avoid; }
"""


def esc(s):
    return html.escape(s, quote=True)


def page_list():
    """Ordered pages: (part, group_title, kind, slug, title)."""
    pages = []
    for tier in (1, 2, 3):
        for slug, t, title, _ in build.TOPICS:
            if t == tier:
                pages.append(("A", TIER_TITLES[tier], "ch6", slug, title))
    for key, gtitle, _, section in build.CARD_GROUPS:
        for slug, grp, title, _ in build.CARDS:
            if grp == key:
                pages.append((SECTION_PART[section], gtitle, "cards", slug, title))
    return pages


LINK_RE = re.compile(r'<a href="([^"]*)">(.*?)</a>', re.S)


def resolve(kind, href, known):
    """Map a link inside a page to an anchor id in the print document, or None."""
    if href.startswith(("http://", "https://", "mailto:")):
        return None
    path, _, frag = href.partition("#")
    base = PurePosixPath("cvr") / build.COLLECTIONS[kind]["dir"][1]
    if not path:
        return ("self", frag)
    parts = []
    for p in (base / path).parts:
        if p == "..":
            parts.pop()
        elif p != ".":
            parts.append(p)
    target = "/".join(parts)
    m = re.fullmatch(r"cvr/(ch6|cards)/([a-z0-9-]+)\.html", target)
    if not m or m.group(2) not in known:
        return None
    return (m.group(2), frag)


class Doc:
    def __init__(self):
        self.markers = []        # marker index -> anchor id
        self.anchor_of = {}      # anchor id -> marker index

    def marker(self, anchor):
        if anchor not in self.anchor_of:
            self.anchor_of[anchor] = len(self.markers)
            self.markers.append(anchor)
        i = self.anchor_of[anchor]
        return f'<span class="pm">QZQ{i}QZQ</span>'

    @staticmethod
    def pref(anchor):
        return f'<span class="pref"> (p.&nbsp;<span class="pnum" data-ref="{anchor}">000</span>)</span>'


def transform_body(doc, kind, slug, body, known):
    body = re.sub(r'\s*<div class="pagefoot">.*?</div>', "", body, flags=re.S)
    body = body.replace("<details ", "<details open ").replace("<details>", "<details open>")
    for old, new in PRINT_WORDING:
        body = body.replace(old, new)
    # prefix ids and references so pages do not clash
    body = re.sub(r'\bid="([^"]+)"', lambda m: f'id="{slug}--{m.group(1)}"', body)
    body = re.sub(r'url\(#([^)]+)\)', lambda m: f"url(#{slug}--{m.group(1)})", body)
    body = re.sub(r'aria-labelledby="([^"]+)"',
                  lambda m: 'aria-labelledby="' + " ".join(f"{slug}--{t}" for t in m.group(1).split()) + '"', body)

    def link(m):
        href, text = m.group(1), m.group(2)
        r = resolve(kind, href, known)
        if r is None:
            return f"<a>{text}</a>" if href.startswith("http") else text
        target, frag = r
        target = slug if target == "self" else target
        anchor = f"{target}--{frag}" if frag else f"{target}--top"
        return f'<a class="xref" href="#{anchor}">{text}</a>{Doc.pref(anchor)}'

    return LINK_RE.sub(link, body)


def collect_targets(pages, known):
    targets = set()
    for _, _, kind, slug, _ in pages:
        _, body = build.parse_source(build.SRC.joinpath(*build.COLLECTIONS[kind]["dir"], f"{slug}.html"))
        for href, _ in LINK_RE.findall(body):
            r = resolve(kind, href, known)
            if r:
                t, frag = r
                t = slug if t == "self" else t
                if frag:
                    targets.add(f"{t}--{frag}")
    return targets


def add_markers(doc, body, targets):
    def rep(m):
        anchor = m.group(2)
        if anchor in targets:
            return m.group(0) + doc.marker(anchor)
        return m.group(0)
    return re.sub(r'(<(?:section|div|h2|h3|h4|p|figure|table|ul|ol)\b[^>]*\bid="([^"]+)"[^>]*>)', rep, body)


def pnum(anchor):
    return f'<span class="pnum" data-ref="{anchor}">000</span>'


def toc_row(title, anchor):
    return f'<div class="toc-row"><span>{esc(title)}</span><span class="lead"></span><span class="pg">{pnum(anchor)}</span></div>'


def part_toc(pages, part):
    """Short contents for a part-divider page."""
    rows, cur_group = [], None
    for p, group, _, slug, title in pages:
        if p != part:
            continue
        if group != cur_group:
            rows.append(f'<p class="toc-group">{esc(group)}</p>')
            cur_group = group
        rows.append(toc_row(title, slug + "--top"))
    return '<div class="part-toc">' + "\n".join(rows) + "</div>"


def build_html(doc, pages):
    known = {slug for _, _, _, slug, _ in pages}
    targets = collect_targets(pages, known)
    css_href = (ROOT / "assets" / "notes.css").as_uri()
    out = [f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>Cardio-Vascular and Respiratory Physiotherapy: complete exam notes</title>
<link rel="stylesheet" href="{css_href}">
<style>{PRINT_CSS}</style>
</head>
<body class="print">
"""]
    # cover (rendered separately, without page numbers)
    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>Cardio-Vascular and Respiratory Physiotherapy</h1>
    <p class="cover__sub">Complete exam notes: Chapter 6 conditions, technique cards, the other syllabus chapters, and exam skills.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Built from</dt><dd>20 MUHS question papers, Summer 2016 to Summer 2026 (code 51413)</dd>
    <dt>Contents</dt><dd>23 Chapter 6 topics and {len(build.CARDS)} cards and chapter pages, with past questions, answer skeletons and self-tests</dd>
    <dt>Content checked</dt><dd>{DATE}</dd>
    <dt>Online version</dt><dd>{SITE_URL}</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Written in original words from current textbooks and dated guidelines; each page lists its sources.</p>
</section>"""

    # front matter
    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use these notes</h1>
  <ol>
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
    <p>Since 2023, ventilated ICU patients appear as long cases and an ICU short question is in every paper.</p>
  </div>
  <h3>How this book is arranged</h3>
  <ul>
    <li><strong>Part A</strong>: the 23 Chapter 6 conditions in three tiers, by how often they are asked.</li>
    <li><strong>Part B</strong>: technique cards (ICU, airway clearance, breathing, oxygen and aerosols, therapy skills, exercise, investigations and scales).</li>
    <li><strong>Part C</strong>: cardiac and pulmonary rehabilitation, the revision chapter (anatomy, physiology, drugs) and basic life support.</li>
    <li><strong>Part D</strong>: answer writing (ICF, goals, documentation) and the practical exam.</li>
  </ul>
  <p>Each topic opens with its syllabus heading, priority, the sessions it was asked in (LAQ = 15-mark long answer, 7m and 3m = short answers; S = Summer, W = Winter, for example S24 = Summer 2024), and the guidelines it was checked against. Page references such as (p. 123) point to related pages. Abbreviations are listed at the end.</p>
</section>"""

    # contents
    toc = ['<section class="toc-print">', "  <h1>Contents</h1>"]
    toc.append("  " + toc_row("How to use these notes", "front--top"))
    toc.append("  " + toc_row("Syllabus map", "smap--top"))
    cur_part, cur_group = None, None
    for part, group, kind, slug, title in pages:
        if part != cur_part:
            ptitle = next(p for p in PARTS if p[0] == part)
            toc.append(f'  <p class="toc-part">Part {part}: {esc(ptitle[1])}</p>')
            cur_part, cur_group = part, None
        if group != cur_group:
            toc.append(f'  <p class="toc-group">{esc(group)}</p>')
            cur_group = group
        toc.append("  " + toc_row(title, slug + "--top"))
    toc.append(f'  <p class="toc-part">Appendix</p>')
    toc.append("  " + toc_row("Abbreviations", "abbr--top"))
    toc.append("</section>")

    # syllabus map
    titles = {slug: title for _, _, _, slug, title in pages}
    smap = ['<section class="smap" id="smap--top">' + doc.marker("smap--top"),
            "  <h1>Syllabus map</h1>",
            "  <p>Where each chapter of the MUHS CVR Physiotherapy syllabus is covered in this book.</p>",
            '  <table><thead><tr><th scope="col">Chapter</th><th scope="col">Syllabus heading</th><th scope="col">Pages in this book</th></tr></thead><tbody>']
    for ch, heading, slugs in SYLLABUS_MAP:
        cells = []
        for s in slugs:
            if s == "@part-A":
                cells.append(f"Part A, all 23 topics (from p.&nbsp;{pnum('partA--top')})")
            else:
                cells.append(f"{esc(titles[s])} (p.&nbsp;{pnum(s + '--top')})")
        smap.append(f'    <tr><th scope="row">{esc(ch)}</th><td>{esc(heading)}</td><td>{"<br>".join(cells)}</td></tr>')
    smap.append("  </tbody></table>")
    smap.append("</section>")

    out_body = [front, "\n".join(toc), "\n".join(smap)]
    cur_part = None
    for part, group, kind, slug, title in pages:
        if part != cur_part:
            p = next(x for x in PARTS if x[0] == part)
            out_body.append(f'<section class="part-page" id="part{part}--top">{doc.marker(f"part{part}--top")}'
                            f'<p class="part-letter">Part {part}</p><h1>{esc(p[1])}</h1><p>{esc(p[2])}</p>'
                            f'{part_toc(pages, part)}</section>')
            cur_part = part
        meta, body = build.parse_source(build.SRC.joinpath(*build.COLLECTIONS[kind]["dir"], f"{slug}.html"))
        body = transform_body(doc, kind, slug, body, known)
        body = add_markers(doc, body, targets)
        coll = build.COLLECTIONS[kind]
        crumb = f'{esc(coll["crumb"])}: {meta["crumb"]}'
        out_body.append(f"""<article class="ptopic" id="{slug}--top">{doc.marker(slug + "--top")}
  <p class="ptopic__crumb">{crumb}</p>
  <h1>{meta['h1']}</h1>
  <p class="lede">{meta['lede']}</p>
  <table class="pmeta"><tbody>
    <tr><th scope="row">Syllabus</th><td>{meta['syllabus']}</td></tr>
    <tr><th scope="row">Priority</th><td>{meta['priority']}</td></tr>
    <tr><th scope="row">Asked as</th><td>{meta['asked']}</td></tr>
    <tr><th scope="row">Usual split</th><td>{meta['split']}</td></tr>
    <tr><th scope="row">Checked against</th><td>{meta['checked']} Content checked {meta['date']}.</td></tr>
  </tbody></table>
{body}
</article>""")

    # abbreviations
    items = sorted(build.ABBR.items(), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><strong>{esc(k)}</strong>: {esc(v)}</p>" for k, v in items]
    abbr += ["  </div>", "</section>"]
    out_body.append("\n".join(abbr))

    body_html = out[0] + "\n".join(out_body) + "\n</body>\n</html>\n"
    cover_html = out[0] + cover + "\n</body>\n</html>\n"
    return body_html, cover_html


# ---------------- Chrome DevTools ----------------
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Chrome:
    def __init__(self):
        self.port = free_port()
        self.profile = tempfile.mkdtemp(prefix="chrome-print-")
        self.proc = subprocess.Popen(
            [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
             "--allow-file-access-from-files", f"--remote-debugging-port={self.port}",
             f"--user-data-dir={self.profile}", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(300):
            try:
                targets = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=2).read())
                page = next(t for t in targets if t.get("type") == "page")
                break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("Chrome did not start")
        self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=900, suppress_origin=True)
        self.next_id = 0

    def call(self, method, **params):
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            if msg.get("method") == "Page.loadEventFired":
                self.loaded = True

    def load(self, url):
        self.loaded = False
        self.call("Page.enable")
        self.call("Page.navigate", url=url)
        while not self.loaded:
            msg = json.loads(self.ws.recv())
            if msg.get("method") == "Page.loadEventFired":
                self.loaded = True
        self.call("Runtime.evaluate", expression="document.fonts.ready.then(() => true)", awaitPromise=True)

    def pdf(self, path, footer=True):
        footer_html = ('<div style="width:100%;font-family:Helvetica,Arial,sans-serif;font-size:7.5pt;color:#5b6773;'
                       'padding:0 14mm;display:flex;justify-content:space-between;">'
                       '<span>Cardio-Vascular and Respiratory Physiotherapy, MUHS IV BPTh</span>'
                       '<span class="pageNumber"></span></div>')
        res = self.call("Page.printToPDF", paperWidth=8.27, paperHeight=11.69,
                        marginTop=0.55, marginBottom=0.7 if footer else 0.55, marginLeft=0.55, marginRight=0.55,
                        printBackground=True, displayHeaderFooter=footer,
                        headerTemplate="<div></div>", footerTemplate=footer_html if footer else "<div></div>",
                        preferCSSPageSize=False, transferMode="ReturnAsStream")
        handle = res["stream"]
        with open(path, "wb") as f:
            while True:
                chunk = self.call("IO.read", handle=handle, size=4 * 1024 * 1024)
                data = chunk.get("data", "")
                f.write(base64.b64decode(data) if chunk.get("base64Encoded") else data.encode("latin-1"))
                if chunk.get("eof"):
                    break
        self.call("IO.close", handle=handle)

    def close(self):
        try:
            self.ws.close()
        finally:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            shutil.rmtree(self.profile, ignore_errors=True)


def page_numbers(pdf_path, doc):
    text = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf_path), "-"], capture_output=True, text=True, check=True).stdout
    found = {}
    for pageno, page in enumerate(text.split("\f"), start=1):
        for m in re.finditer(r"QZQ(\d+)QZQ", page.replace(" ", "")):
            found.setdefault(doc.markers[int(m.group(1))], pageno)
    return found


def fill(html_text, numbers):
    missing = set()

    def rep(m):
        anchor = m.group(1)
        if anchor in numbers:
            return f'<span class="pnum" data-ref="{anchor}">{numbers[anchor]}</span>'
        top = anchor.split("--")[0] + "--top"
        if top in numbers:
            return f'<span class="pnum" data-ref="{anchor}">{numbers[top]}</span>'
        missing.add(anchor)
        return m.group(0)
    out = re.sub(r'<span class="pnum" data-ref="([^"]+)">000</span>', rep, html_text)
    return out, missing


def main():
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    pages = page_list()
    doc = Doc()
    body_html, cover_html = build_html(doc, pages)
    work = Path(tempfile.mkdtemp(prefix="cvr-print-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    body_file.write_text(body_html, encoding="utf-8")
    chrome = Chrome()
    try:
        chrome.load(body_file.as_uri())
        chrome.pdf(work / "pass1.pdf")
        numbers = page_numbers(work / "pass1.pdf", doc)
        final_html, missing = fill(body_html, numbers)
        if missing:
            print(f"warning: no page found for {len(missing)} anchors, e.g. {sorted(missing)[:5]}")
        body_file.write_text(final_html, encoding="utf-8")
        chrome.load(body_file.as_uri())
        chrome.pdf(work / "body.pdf")
        check = page_numbers(work / "body.pdf", doc)
        moved = [a for a in numbers if check.get(a) != numbers[a]]
        if moved:
            print(f"warning: {len(moved)} anchors moved between passes, e.g. {moved[:5]}")
        chrome.load(cover_file.as_uri())
        chrome.pdf(work / "cover.pdf", footer=False)
    finally:
        chrome.close()
    subprocess.run(["pdfunite", str(work / "cover.pdf"), str(work / "body.pdf"), str(out_pdf)], check=True)
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((l for l in info.splitlines() if l.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, "
          f"{out_pdf.stat().st_size / 1e6:.1f} MB); markers found {len(numbers)} of {len(doc.markers)}")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
