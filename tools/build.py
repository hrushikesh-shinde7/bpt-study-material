#!/usr/bin/env python3
"""Build the notes site.

Page content lives in src/<path>.html: a metadata comment followed by the
<section class="sec"> blocks. This script wraps each source in the shared
page frame (top bar, contents menu, header and case sheet, previous/next
links) and regenerates index.html from the topic list below.

Run from anywhere:  python3 tools/build.py
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Ordered topic list for CVR Chapter 6. A topic is "ready" when its source exists.
TOPICS = [
    # slug, tier, title, meta line on the home page
    ("ihd-mi-cabg", 1, "IHD, myocardial infarction, angioplasty and CABG, with cardiac rehab", "6(a). In 11 of 12 papers; the most common long answer."),
    ("burns", 1, "Burns: acute care, positioning, splinting and inhalation injury", "6(g). In all 12 papers."),
    ("pad", 1, "Peripheral arterial disease, Buerger's disease and other arterial disorders", "6(a). In all 12 papers."),
    ("copd", 1, "COPD: chronic bronchitis and emphysema", "6(b). In 9 papers."),
    ("bronchiectasis", 1, "Bronchiectasis, including after TB", "6(c). In 9 papers."),
    ("mastectomy", 1, "Mastectomy, lymphoedema and cancer surgery", "6(f). In 9–10 papers."),
    ("venous", 1, "Varicose veins, venous ulcer, DVT and thrombophlebitis", "6(a). In 8 papers."),
    ("lung-surgery", 1, "Lung surgery, thoracotomy, chest drain and chest trauma", "6(e). In 8 papers."),
    ("amputation", 1, "Amputation and stump care", "6(h). In 7 papers."),
    ("asthma", 1, "Asthma in adults and children", "6(b), 6(d). In 6 papers."),
    ("diabetes", 2, "Diabetes, diabetic foot, wound healing and diabetes insipidus", "6(h), 6(i)"),
    ("obesity", 2, "Obesity and metabolic syndrome", "6(i)"),
    ("abdominal-surgery", 2, "Abdominal surgery: pre- and post-operative care", "6(f)"),
    ("tb", 2, "Tuberculosis, thoracoplasty and post-TB lung disease", "6(c)"),
    ("ild", 2, "Interstitial and occupational lung disease", "6(b)"),
    ("pleural", 2, "Pleural effusion, pneumothorax, empyema and pleurisy", "6(c)"),
    ("hypertension", 2, "Hypertension", "6(a). Rarely asked alone, but part of many cases."),
    ("valvular-acquired", 2, "Valve disease, heart failure, cardiomyopathy, pacemaker and ICD", "6(a)"),
    ("congenital", 2, "Congenital heart disease: tetralogy of Fallot, ASD, VSD, PDA", "6(a)"),
    ("pneumonia", 3, "Pneumonia, lung abscess and atelectasis", "6(c)"),
    ("paediatric", 3, "Neonatal and paediatric respiratory conditions", "6(d)"),
    ("cystic-fibrosis", 3, "Cystic fibrosis", "6(b), 6(d)"),
    ("chest-wall", 3, "Flail chest, scoliosis and kyphosis", "6(j)"),
]

# Abbreviations explained automatically at their first use on each page.
# Page-specific or ambiguous ones (ICD, PT for posterior tibial) are written by hand with <abbr>.
ABBR = {
    "PT": "Physiotherapy", "ICF": "International Classification of Functioning, Disability and Health",
    "ROM": "Range of motion", "ADL": "Activities of daily living", "ACBT": "Active cycle of breathing technique",
    "DVT": "Deep vein thrombosis", "PE": "Pulmonary embolism", "COPD": "Chronic obstructive pulmonary disease",
    "ICU": "Intensive care unit", "TBSA": "Total body surface area", "ABG": "Arterial blood gas",
    "ECG": "Electrocardiogram", "HR": "Heart rate", "BP": "Blood pressure", "RR": "Respiratory rate",
    "RPE": "Rating of perceived exertion (Borg scale)", "METs": "Metabolic equivalents (1 MET = resting energy use)",
    "PFT": "Pulmonary function test", "ABI": "Ankle–brachial index", "ABPI": "Ankle–brachial pressure index",
    "PAD": "Peripheral arterial disease", "PCI": "Percutaneous coronary intervention (angioplasty)",
    "CABG": "Coronary artery bypass grafting", "MI": "Myocardial infarction", "IHD": "Ischaemic heart disease",
    "EF": "Ejection fraction", "MCP": "Metacarpophalangeal", "PIP": "Proximal interphalangeal",
    "VAS": "Visual analogue scale", "NRS": "Numeric rating scale", "FIM": "Functional Independence Measure",
    "ARDS": "Acute respiratory distress syndrome", "mMRC": "Modified Medical Research Council dyspnoea scale",
    "NYHA": "New York Heart Association", "6MWT": "Six-minute walk test", "PEP": "Positive expiratory pressure",
    "IMT": "Inspiratory muscle training", "TENS": "Transcutaneous electrical nerve stimulation",
    "LAQ": "Long-answer question", "BMI": "Body mass index", "HbA1c": "Glycated haemoglobin (3-month blood sugar)",
    "TB": "Tuberculosis", "ILD": "Interstitial lung disease", "GTN": "Glyceryl trinitrate (nitroglycerin)",
    "LAD": "Left anterior descending artery", "LIMA": "Left internal mammary artery", "RIMA": "Right internal mammary artery",
    "FEV1": "Forced expiratory volume in 1 second", "FVC": "Forced vital capacity", "SpO₂": "Oxygen saturation by pulse oximeter",
    "PaO₂": "Arterial oxygen pressure", "PaCO₂": "Arterial carbon dioxide pressure", "HRR": "Heart-rate reserve",
    "1RM": "One-repetition maximum", "CR": "Cardiac rehabilitation", "STG": "Short-term goals", "LTG": "Long-term goals",
    "MRM": "Modified radical mastectomy", "BKA": "Below-knee amputation", "AKA": "Above-knee amputation",
    "CVC": "Central venous catheter", "NIV": "Non-invasive ventilation", "CPAP": "Continuous positive airway pressure",
    "PEEP": "Positive end-expiratory pressure", "SIMV": "Synchronised intermittent mandatory ventilation",
    "IPPB": "Intermittent positive pressure breathing", "CXR": "Chest X-ray", "HRCT": "High-resolution CT scan",
    "DM": "Diabetes mellitus", "HTN": "Hypertension", "CHD": "Coronary heart disease", "CAD": "Coronary artery disease",
}


def add_abbr(body):
    """Wrap the first plain-text use of each known abbreviation in <abbr>."""
    done = set(re.findall(r"<abbr[^>]*>([^<]+)</abbr>", body))
    parts = re.split(r"(<svg.*?</svg>|<abbr.*?</abbr>|<summary.*?</summary>|<h2.*?</h2>|<[^>]+>)", body, flags=re.S)
    for i in range(0, len(parts), 2):
        text = parts[i]
        hits = []
        for ab, full in ABBR.items():
            if ab in done:
                continue
            m = re.search(r"(?<![\w-])" + re.escape(ab) + r"(?![\w-])", text)
            if m and not any(m.start() < e and s < m.end() for s, e, _, _ in hits):
                hits.append((m.start(), m.end(), ab, full))
        for s, e, ab, full in sorted(hits, reverse=True):
            text = text[:s] + f'<abbr title="{html.escape(full)}">{ab}</abbr>' + text[e:]
            done.add(ab)
        parts[i] = text
    return "".join(parts)


TRACE = "M0 9" + "h20q4 -3 8 0h8l3 2l3 -10l3 12l3 -4h12q6 -5 12 0h28" * 10

HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="stylesheet" href="{up}assets/notes.css">
<script>
  /* set theme before paint to avoid a flash */
  try {{ var t = localStorage.getItem("notes-theme"); if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t); }} catch (e) {{}}
</script>
</head>
<body>
"""

THEME_BTN = ('<button class="iconbtn js-theme" type="button"><svg viewBox="0 0 24 24" aria-hidden="true">'
             '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z" fill="currentColor"/></svg><span>Dark</span></button>')


def parse_source(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--(.*?)-->\s*(.*)\Z", text, re.S)
    if not m:
        sys.exit(f"{path}: missing metadata comment")
    meta = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    for key in ("title", "h1", "crumb", "description", "lede", "syllabus", "priority", "asked", "split", "checked", "date", "review"):
        if key not in meta:
            sys.exit(f"{path}: metadata is missing '{key}'")
    return meta, m.group(2).rstrip() + "\n"


def toc_items(body):
    items = []
    pat = r'<section class="sec[^"]*" id="([^"]+)"(?: data-toc="([^"]*)")?>\s*<h2><span class="n">([^<]*)</span>(.*?)</h2>'
    for sid, short, num, label in re.findall(pat, body, re.S):
        label = short or re.sub(r"<[^>]+>", "", label).strip()
        items.append((sid, num, label))
    return items


def build_page(slug, ready_slugs):
    meta, body = parse_source(SRC / "cvr" / "ch6" / f"{slug}.html")
    body = add_abbr(body)
    up = "../../"
    toc = "\n".join(
        f'    <li><a href="#{sid}"><span class="n">{num}</span>{html.escape(label)}</a></li>'
        for sid, num, label in toc_items(body)
    )
    i = ready_slugs.index(slug)
    prev_s = ready_slugs[i - 1] if i > 0 else None
    next_s = ready_slugs[i + 1] if i + 1 < len(ready_slugs) else None
    titles = {s: t for s, _, t, _ in TOPICS}
    nav = []
    if prev_s:
        nav.append(f'<a class="pagenav__prev" href="{prev_s}.html"><span>Previous topic</span>{html.escape(titles[prev_s])}</a>')
    if next_s:
        nav.append(f'<a class="pagenav__next" href="{next_s}.html"><span>Next topic</span>{html.escape(titles[next_s])}</a>')
    pagenav = f'  <nav class="pagenav" aria-label="Other topics">\n    {"".join(nav)}\n  </nav>\n' if nav else ""

    out = HEAD.format(title=html.escape(meta["title"]), description=html.escape(meta["description"]), up=up)
    out += f"""<a class="skip" href="#content">Skip to notes</a>

<header class="topbar">
  <button class="iconbtn js-toc-btn" type="button" aria-controls="toc" aria-expanded="false">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    Contents
  </button>
  <div class="topbar__title"><a href="{up}index.html">CVR Physiotherapy</a></div>
  {THEME_BTN}
  <svg class="trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{TRACE}"/></svg>
</header>

<div class="layout">
<nav class="toc" id="toc" aria-label="Contents of this page">
  <h2>On this page</h2>
  <ol>
{toc}
  </ol>
  <div class="toc__extra">
    <a href="{up}index.html">All Chapter 6 topics</a>
  </div>
</nav>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs"><a href="{up}index.html">CVR Physiotherapy</a> › Chapter 6 › {meta['crumb']}</p>
      <h1>{meta['h1']}</h1>
      <p class="lede">{meta['lede']}</p>

      <div class="casesheet">
        <dl>
          <div class="row"><dt>Syllabus</dt><dd>{meta['syllabus']}</dd></div>
          <div class="row"><dt>Priority</dt><dd>{meta['priority']}</dd></div>
          <div class="row"><dt>Asked as</dt><dd>{meta['asked']}</dd></div>
          <div class="row"><dt>Usual split</dt><dd>{meta['split']}</dd></div>
          <div class="row"><dt>Checked against</dt><dd>{meta['checked']}</dd></div>
          <div class="row"><dt>Content checked</dt><dd>{meta['date']}. Next review due {meta['review']}.</dd></div>
          <div class="row"><dt>My revision</dt><dd>
            <div class="tracker">
              <label><input type="checkbox" class="js-track" value="read"> Read once</label>
              <label><input type="checkbox" class="js-track" value="t1"> Self-test day 1</label>
              <label><input type="checkbox" class="js-track" value="t7"> Day 7</label>
              <label><input type="checkbox" class="js-track" value="t21"> Day 21</label>
            </div>
          </dd></div>
        </dl>
      </div>
    </div>
  </div>

  <div class="wrap">

{body}
{pagenav}  </div>
</main>
</div>

<script src="{up}assets/notes.js"></script>
</body>
</html>
"""
    dest = ROOT / "cvr" / "ch6" / f"{slug}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")


def build_index(ready):
    def row(slug, title, note):
        if slug in ready:
            return (f'        <li><a class="ttl" href="cvr/ch6/{slug}.html">{html.escape(title)}</a>'
                    f'<span class="status status--ready">Ready</span><span class="meta">{html.escape(note)}</span></li>')
        return (f'        <li><span class="ttl">{html.escape(title)}</span>'
                f'<span class="status status--soon">Coming</span><span class="meta">{html.escape(note)}</span></li>')

    tiers = {1: [], 2: [], 3: []}
    for slug, tier, title, note in TOPICS:
        tiers[tier].append(row(slug, title, note))
    done = len(ready)
    total = len(TOPICS)

    out = HEAD.format(title="CVR Physiotherapy notes",
                      description="Exam notes for MUHS final-year BPTh Cardio-Vascular and Respiratory Physiotherapy, built from the real past papers.",
                      up="")
    out += f"""<a class="skip" href="#content">Skip to topics</a>
<header class="topbar">
  <div class="topbar__title">CVR Physiotherapy</div>
  {THEME_BTN}
</header>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs">MUHS IV BPTh</p>
      <h1>Cardio-Vascular and Respiratory Physiotherapy</h1>
      <p class="lede">Chapter 6, Physiotherapy Management. Topics are listed in the order they score in the real papers, not the syllabus order. {done} of {total} topics ready.</p>
    </div>
  </div>

  <div class="wrap">
    <section class="sec" id="how">
      <h2><span class="n">?</span>How to use these notes</h2>
      <ol>
        <li><strong>Read a page once</strong>, slowly. Open every "Why?" button.</li>
        <li><strong>Close it and recall.</strong> Write the keywords and draw the diagrams on paper from memory, then compare.</li>
        <li><strong>Test yourself</strong> with the questions at the end of the page. Answer before you open the answer.</li>
        <li><strong>Come back</strong> on day 1, day 7 and day 21, and tick the boxes at the top of the page. Testing yourself again beats re-reading.</li>
      </ol>
      <div class="note note--exam">
        <span class="note__label">What the real paper looks like (12 papers, 2016–2022)</span>
        <p>80 marks in 3 hours. <strong>No MCQs</strong>, even though the syllabus printed a scheme with them.</p>
        <ul>
          <li>Short answers: any 5 of 6 at <strong>3 marks</strong>, and any 5 of 6 at <strong>7 marks</strong>.</li>
          <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. Every option is a patient case, and almost all start with ICF.</li>
        </ul>
        <p>No paper after Winter 2022 has been found yet. Check the latest papers with your college library or seniors.</p>
      </div>
    </section>

    <section class="sec" id="tier1">
      <h2><span class="n">1</span>Tier 1: full notes, asked almost every year</h2>
      <ul class="chapter-list">
{chr(10).join(tiers[1])}
      </ul>
    </section>

    <section class="sec" id="tier2">
      <h2><span class="n">2</span>Tier 2: asked sometimes</h2>
      <ul class="chapter-list">
{chr(10).join(tiers[2])}
      </ul>
    </section>

    <section class="sec" id="tier3">
      <h2><span class="n">3</span>Tier 3: short notes, not asked on their own in 2016–2022</h2>
      <p>The papers say any syllabus topic can be asked, so these still get their own page.</p>
      <ul class="chapter-list">
{chr(10).join(tiers[3])}
      </ul>
    </section>

    <section class="sec" id="cards">
      <h2><span class="n">4</span>Technique cards and exam skills</h2>
      <p>About 4 in 10 short-answer options test techniques rather than conditions. These pages will follow: ACBT, PEP and flutter devices, suctioning, ventilator modes, humidification and nebulisation, oxygen therapy, energy conservation, exercise testing, Borg, NYHA and MET scales, breathing exercises and postural drainage. An answer-writing guide and a practical-exam pack are also planned.</p>
    </section>

    <div class="pagefoot">
      <p>Educational notes for exam preparation. Not medical advice. Written in original words from current textbooks and dated guidelines; sources are listed on each page.</p>
    </div>
  </div>
</main>
<script src="assets/notes.js"></script>
</body>
</html>
"""
    (ROOT / "index.html").write_text(out, encoding="utf-8")


def main():
    ready = [s for s, *_ in TOPICS if (SRC / "cvr" / "ch6" / f"{s}.html").exists()]
    for slug in ready:
        build_page(slug, ready)
    build_index(set(ready))
    print(f"built {len(ready)} of {len(TOPICS)} topics: {', '.join(ready)}")


if __name__ == "__main__":
    main()
