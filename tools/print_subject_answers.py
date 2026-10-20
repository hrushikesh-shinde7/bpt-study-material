#!/usr/bin/env python3
"""Build the printable A4 book of model answers to the 3- and 7-mark questions
for Neuro or Community, in the same format as tools/print_answers.py (CVR).

Answers live in src/<subject>/answers/<slug>.html, one file per topic (same
slugs as the full pages). Each question is an <article class="qa"> with
data-marks (3 or 7) and data-asked (paper codes such as "S17-1b W17-1f").
A diagram from the full notes can be embedded with
<div class="figref" data-fig="5a-a-stroke#stf1t"></div> (the id of the
figure's title). Build the subject's full notes first (tools/print_subject.py),
then:

    python tools/print_subject_answers.py neuro [output.pdf]
    python tools/print_subject_answers.py community [output.pdf]
"""
import html
import importlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
import print_answers as pa  # noqa: E402
import print_pdf as pp  # noqa: E402
import print_short as ps  # noqa: E402
import print_subject as psub  # noqa: E402


def esc(s):
    return html.escape(s, quote=True)


# Extra abbreviations for the printed lists only (the website spells these out in the text).
PRINT_ABBR = {
    "AAM": "Ayushman Arogya Mandir", "ACOG": "American College of Obstetricians and Gynecologists",
    "ADAPT": "Able Disabled All People Together (formerly the Spastics Society of India)",
    "AIIMS": "All India Institute of Medical Sciences", "ANOVA": "Analysis of variance",
    "BIA": "Bioelectrical impedance analysis", "BMR": "Basal metabolic rate",
    "BMVSS": "Bhagwan Mahaveer Viklang Sahayata Samiti (Jaipur foot)", "CTRI": "Clinical Trials Registry–India",
    "DDMA": "District Disaster Management Authority", "DDRC": "District Disability Rehabilitation Centre",
    "DEIC": "District Early Intervention Centre", "EMG": "Electromyography",
    "ESI": "Employees' State Insurance", "ESIC": "Employees' State Insurance Corporation",
    "FES-I": "Falls Efficacy Scale–International", "FINER": "Feasible, interesting, novel, ethical, relevant (a good research question)",
    "FITT-VP": "Frequency, intensity, time, type, volume and progression", "FSH": "Follicle-stimulating hormone",
    "GDS": "Geriatric Depression Scale", "GMFCS": "Gross Motor Function Classification System",
    "IADL": "Instrumental activities of daily living", "IAP": "Indian Academy of Pediatrics (growth charts)",
    "IARC": "International Agency for Research on Cancer", "ICDS": "Integrated Child Development Services",
    "ICIDH": "International Classification of Impairments, Disabilities and Handicaps (WHO, 1980)",
    "ICIQ": "International Consultation on Incontinence Questionnaire", "ICRC": "International Committee of the Red Cross",
    "ICRP": "International Commission on Radiological Protection", "ICT": "Information and communication technology",
    "IEA": "International Ergonomics Association", "IGNOAPS": "Indira Gandhi National Old Age Pension Scheme",
    "ILO": "International Labour Organization", "JSSK": "Janani Shishu Suraksha Karyakram", "JSY": "Janani Suraksha Yojana",
    "LH": "Luteinising hormone", "MNA": "Mini Nutritional Assessment", "MRI": "Magnetic resonance imaging",
    "MSDs": "Musculoskeletal disorders", "NCD": "Non-communicable disease", "NDFDC": "National Divyangjan Finance and Development Corporation",
    "NDI": "Neck Disability Index", "NDRF": "National Disaster Response Force", "NFHS-5": "National Family Health Survey, fifth round (2019–21)",
    "NICE": "National Institute for Health and Care Excellence (UK)", "NIOSH": "National Institute for Occupational Safety and Health (USA)",
    "NLEP": "National Leprosy Eradication Programme", "NPCBVI": "National Programme for Control of Blindness and Visual Impairment",
    "NPHCE": "National Programme for Health Care of the Elderly", "NPPCD": "National Programme for Prevention and Control of Deafness",
    "NPRS": "Numeric Pain Rating Scale", "OCRA": "Occupational Repetitive Actions index", "OWAS": "Ovako Working Posture Analysis System",
    "PCPNDT": "Pre-Conception and Pre-Natal Diagnostic Techniques (Act)", "PERFECT": "Power, endurance, repetitions, fast contractions, every contraction timed (pelvic floor grading)",
    "PFMT": "Pelvic floor muscle training", "PICO": "Population, intervention, comparison, outcome", "PM-JAY": "Pradhan Mantri Jan Arogya Yojana",
    "PMF": "Progressive massive fibrosis", "PMMVY": "Pradhan Mantri Matru Vandana Yojana", "PMSMA": "Pradhan Mantri Surakshit Matritva Abhiyan",
    "POMA": "Performance-Oriented Mobility Assessment (Tinetti)", "POP-Q": "Pelvic Organ Prolapse Quantification",
    "QEC": "Quick Exposure Check", "RBSK": "Rashtriya Bal Swasthya Karyakram", "RCT": "Randomised controlled trial",
    "SDMA": "State Disaster Management Authority", "SPPB": "Short Physical Performance Battery", "SSI": "Spastics Society of India (now ADAPT)",
    "START": "Simple Triage and Rapid Treatment", "UIP": "Universal Immunisation Programme", "UN": "United Nations",
    "UNESCO": "United Nations Educational, Scientific and Cultural Organization", "UTI": "Urinary tract infection", "UV": "Ultraviolet",
    "YMCA": "Young Men's Christian Association",
}


def index_label(title):
    """Short label for the paper index: drop bracketed asides, keep the part
    before the first colon or semicolon."""
    t = re.sub(r"<[^>]+>", "", title)
    t = re.sub(r"\s*\([^)]*\)", "", t)
    return re.split(r": |; ", t)[0]


def load_topics(mod, answers_dir):
    """[(part, slug, title, [articles])] in syllabus order."""
    out = []
    for slug, code, title, part, _ in mod.PAGES:
        f = answers_dir / f"{slug}.html"
        if not f.exists():
            continue
        arts = []
        for aid, marks, asked, h3, body in pa.ARTICLE_RE.findall(f.read_text(encoding="utf-8")):
            arts.append(dict(id=aid, marks=int(marks), asked=asked.split(), title=h3.strip(), body=body.strip(), slug=slug))
        if f.read_text(encoding="utf-8").count('<article class="qa"') != len(arts):
            sys.exit(f"{f}: an article does not match the expected markup")
        arts.sort(key=lambda a: a["marks"])
        out.append((part, slug, f"{code} {title}" if code != "Exam" else title, arts))
    return out


FIG_CACHE = {}


def figure_html(src_dir, ref, n):
    page, _, fid = ref.partition("#")
    if page not in FIG_CACHE:
        FIG_CACHE[page] = (src_dir / f"{page}.html").read_text(encoding="utf-8")
    m = re.search(r'<figure class="fig" aria-labelledby="' + re.escape(fid) + r'">.*?</figure>', FIG_CACHE[page], re.S)
    if not m:
        sys.exit(f"figure {ref} not found")
    fig = m.group(0)
    pre = f"af{n}-"
    fig = re.sub(r'\bid="([^"]+)"', lambda mm: f'id="{pre}{mm.group(1)}"', fig)
    fig = re.sub(r'url\(#([^)]+)\)', lambda mm: f"url(#{pre}{mm.group(1)})", fig)
    fig = re.sub(r'(xlink:href|href)="#([^"]+)"', lambda mm: f'{mm.group(1)}="#{pre}{mm.group(2)}"', fig)
    fig = re.sub(r'aria-labelledby="([^"]+)"', lambda mm: 'aria-labelledby="' + " ".join(pre + t for t in mm.group(1).split()) + '"', fig)
    fig = re.sub(r'<button[^>]*js-sketch[^>]*>.*?</button>', "", fig, flags=re.S)
    fig = re.sub(r'<details class="why"><summary>Text version.*?</details>', "", fig, flags=re.S)
    for old, new in pp.PRINT_WORDING:
        fig = fig.replace(old, new)
    return fig


def expand_figrefs(src_dir, body, counter):
    def rep(m):
        counter[0] += 1
        wide = " wide" if "data-wide" in m.group(0) else ""
        return f'<div class="figwrap{wide}">{figure_html(src_dir, m.group(1), counter[0])}</div>'
    return re.sub(r'<div class="figref" data-fig="([^"]+)"[^>]*></div>', rep, body)


def full_notes_pages(cfg, mod):
    pdf = build.ROOT.parent / "PDF" / f"{cfg['file']} - complete notes (print).pdf"
    if not pdf.exists():
        print("note: full-notes PDF not found, so answers will not show its page numbers")
        return {}
    if pdf.stat().st_mtime < max(p.stat().st_mtime for p in mod.SRC.glob("*.html")):
        print("warning: the full-notes PDF is older than the page sources; rebuild it first so page numbers match")
    doc = pp.Doc()
    psub.build_html(doc, cfg, mod)
    found = pp.page_numbers(pdf, doc)
    return {a[: -len("--top")]: n - 1 for a, n in found.items() if a.endswith("--top")}   # page 1 is the cover


def build_html(doc, cfg, mod, topics, full_pages):
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>{esc(cfg['name'])}: 3- and 7-mark answers</title>
<link rel="stylesheet" href="{(build.ROOT / "assets" / "notes.css").as_uri()}">
<link rel="stylesheet" href="{(build.ROOT / "assets" / "syllabus.css").as_uri()}">
<style>{ps.SHORT_CSS}{pa.ANSWERS_CSS}.part-head {{ break-before: auto; margin-top: 3mm; }} .ans ol {{ padding-left: 4.8mm; }}</style>
</head>
<body class="print">
"""
    all_arts = [a for *_, arts in topics for a in arts]
    n3 = sum(1 for a in all_arts if a["marks"] == 3)
    n7 = len(all_arts) - n3
    n_slots = len({c for a in all_arts for c in a["asked"]})
    known_q = {a["id"]: f'q-{a["slug"]}-{a["id"]}' for a in all_arts}
    known_topics = {t[1] for t in topics}
    parts = {p[0]: p for p in mod.PARTS}

    def part_label(key):
        return f"Part {key}: {parts[key][1]}" if key != "E" else parts[key][1]

    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>{esc(cfg['name'])}</h1>
    <p class="cover__sub">Model answers to every 3-mark and 7-mark question asked from Summer 2016 to Summer 2026, written the way to write them in the exam.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Questions</dt><dd>All {n_slots} short-answer slots of the 20 papers (code {cfg['code']}): {n3} distinct 3-mark and {n7} distinct 7-mark questions after merging repeats</dd>
    <dt>Arranged</dt><dd>By topic, in syllabus order, with an index by paper at the end</dd>
    <dt>Online version</dt><dd>{pp.SITE_URL}{cfg['folder']}/</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Every answer is drawn from the full notes, which list the sources for each fact.</p>
</section>"""

    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use the model answers</h1>
  <p>Every short-answer question from the 20 MUHS papers (Summer 2016 to Summer 2026) is here, once. When a question was repeated, the sessions are listed under it, so you can see which ones come back.</p>
  <ol>
    <li><b>Read the question, close the book, write your own answer</b> in the time allowed, then compare. Copying without recall does not stick.</li>
    <li><b>Learn the structure</b> as much as the facts: definition, points, table or diagram, physiotherapy, one closing line.</li>
    <li><b>Practise whole papers.</b> The index at the back lists each paper's short questions with the page of every answer: sit one paper in 100 minutes, then mark it.</li>
  </ol>
  <h2>What examiners look for</h2>
  <table class="marks-table">
    <thead><tr><th>Question</th><th>Length and time</th><th>Structure</th></tr></thead>
    <tbody>
      <tr><td><b>3 marks</b> (any 5 of 6)</td><td>Half a page; about 6 minutes</td><td>One-line definition, then 3–5 points, a small table or a labelled sketch; one line of physiotherapy relevance</td></tr>
      <tr><td><b>7 marks</b> (any 5 of 6)</td><td>One and a half to two pages; about 14 minutes</td><td>Definition or introduction; classification or features; 6–8 headed points or a table with doses; a labelled diagram; precautions; one closing line</td></tr>
    </tbody>
  </table>
  <p>Write <b>doses with units</b> and <b>underline the keywords</b>. A <b>"Draw"</b> line tells you which diagram to draw; where the full notes have it, the diagram is printed beside the answer.</p>
  <p class="ask"><b>The paper:</b> 80 marks in 3 hours. Q1: any 5 of 6 at 3 marks (15). Q2: any 5 of 6 at 7 marks (35). Q3 and Q4: one 15-mark long answer each (30). About 2 minutes a mark. The long answers are covered in the full notes.</p>
</section>"""

    toc = ['<section class="toc-print">', "  <h1>Contents</h1>", '  <div class="toc-cols">']
    cur = None
    for part, slug, title, arts in topics:
        if part != cur:
            toc.append(f'  <p class="toc-part">{esc(part_label(part))}</p>')
            cur = part
        n = ", ".join(f"{c} × {m}" for m in (3, 7) if (c := sum(1 for a in arts if a["marks"] == m)))
        toc.append("  " + pp.toc_row(f"{title} ({n})", f"{slug}--top"))
    toc.append("  " + pp.toc_row("Index by paper", "paper-index--top"))
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc += ["  </div>", "</section>"]

    body = ['<section class="sheet" id="answers--top">' + doc.marker("answers--top"), '<div class="book">']
    counter = [0]
    cur = None
    for part, slug, title, arts in topics:
        if part != cur:
            body.append(f'<p class="part-head">{esc(part_label(part))}</p>')
            cur = part
        full = f'<span class="full">Full notes p.&nbsp;{full_pages[slug]}</span>' if slug in full_pages else ""
        body.append(f'<div class="topic-head" id="{slug}--top">{doc.marker(slug + "--top")}<h2>{esc(title)}</h2>{full}</div>')
        for a in arts:
            anchor = known_q[a["id"]]
            asked = ", ".join(pa.code_label(c) for c in a["asked"])
            times = len(a["asked"])
            times_txt = f" (asked {times} times)" if times > 1 else ""
            ans = expand_figrefs(mod.SRC, a["body"], counter)
            ans = pa.link_answers(ans, known_q, known_topics)
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
          "  <p>Each paper's short questions (Q1 at 3 marks, Q2 at 7 marks) with the page of the model answer. Sit a paper in 100 minutes (five of each), then check.</p>",
          '  <div class="pi-cols">']
    for p in pa.PAPERS:
        rows = []
        for q in ("1", "2"):
            for letter in "abcdefg":
                a = by_code.get(f"{p}-{q}{letter}")
                if a:
                    rows.append(f'    <div class="pi-row"><span class="q">{q}{letter}</span><span>{esc(index_label(a["title"]))}</span>'
                                f'<span class="lead"></span><span class="pg">{pp.pnum(known_q[a["id"]])}</span></div>')
        if rows:
            pi.append(f'  <div class="pi-paper"><h3>{names[p[0]]} 20{p[1:]}</h3>')
            pi += rows
            pi.append("  </div>")
    pi += ["  </div>", "</section>"]

    text = " ".join(re.sub(r"<[^>]+>", " ", a["title"] + " " + a["body"]) for a in all_arts)
    merged = {**PRINT_ABBR, **ps.SHORT_ABBR, **build.ABBR}
    used = sorted(((k, v) for k, v in merged.items() if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", text)), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>", '  <div class="abbr-cols">']
    abbr += [f"    <p><b>{esc(k)}</b>: {esc(v)}</p>" for k, v in used]
    abbr += ["  </div>", "</section>"]

    page = head + "\n".join([front, "\n".join(toc), "\n".join(body), "\n".join(pi), "\n".join(abbr)]) + "\n</body>\n</html>\n"
    return page, head + cover + "\n</body>\n</html>\n"


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in psub.SUBJECTS:
        sys.exit("usage: print_subject_answers.py neuro|community [output.pdf]")
    cfg = psub.SUBJECTS[sys.argv[1]]
    mod = importlib.import_module(cfg["module"])
    build.ABBR = {**build.ABBR, **getattr(mod, cfg["abbr"])}
    out_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else build.ROOT.parent / "PDF" / f"{cfg['file']} - 3 and 7 mark answers (print).pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    topics = load_topics(mod, mod.SRC / "answers")
    arts = [a for *_, al in topics for a in al]
    codes = [c for a in arts for c in a["asked"]]
    dup = sorted({c for c in codes if codes.count(c) > 1})
    if dup:
        sys.exit(f"paper codes used by more than one answer: {dup}")
    ids = [a["id"] for a in arts]
    if len(ids) != len(set(ids)):
        sys.exit("duplicate answer ids")
    full_pages = full_notes_pages(cfg, mod)
    doc = pp.Doc()
    body_html, cover_html = build_html(doc, cfg, mod, topics, full_pages)
    work = Path(tempfile.mkdtemp(prefix=f"{sys.argv[1]}-answers-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    footer = f"{cfg['name']} model answers, MUHS IV BPTh"
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
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((line for line in info.splitlines() if line.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, {out_pdf.stat().st_size / 1e6:.1f} MB); "
          f"{len(arts)} questions in {len(topics)} topics, {len(set(codes))} paper slots")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
