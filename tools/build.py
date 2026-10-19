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
    ("ihd-mi-cabg", 1, "IHD, myocardial infarction, angioplasty and CABG, with cardiac rehab", "6(a). In 18 of 20 papers; the most common long answer (16 cases)."),
    ("burns", 1, "Burns: acute care, positioning, splinting and inhalation injury", "6(g). In 19 of 20 papers; 12 long answers."),
    ("mastectomy", 1, "Mastectomy, lymphoedema and cancer surgery", "6(f). In 16 of 20 papers; 6 long answers."),
    ("pad", 1, "Peripheral arterial disease, Buerger's disease and other arterial disorders", "6(a). In 18 of 20 papers, mostly ABI and short answers."),
    ("copd", 1, "COPD: chronic bronchitis and emphysema", "6(b). In 13 of 20 papers."),
    ("lung-surgery", 1, "Lung surgery, thoracotomy, chest drain and chest trauma", "6(e). In 12 of 20 papers."),
    ("bronchiectasis", 1, "Bronchiectasis, including after TB", "6(c). In 11 of 20 papers."),
    ("amputation", 1, "Amputation and stump care", "6(h). In 11 of 20 papers."),
    ("venous", 1, "Varicose veins, venous ulcer, DVT and thrombophlebitis", "6(a). In 11 of 20 papers."),
    ("asthma", 1, "Asthma in adults and children", "6(b), 6(d). In 10 of 20 papers."),
    ("abdominal-surgery", 2, "Abdominal surgery: pre- and post-operative care", "6(f). In 9 of 20 papers, as short answers."),
    ("diabetes", 2, "Diabetes, diabetic foot, wound healing, pressure sores and diabetes insipidus", "6(h), 6(i)"),
    ("obesity", 2, "Obesity and metabolic syndrome", "6(i)"),
    ("tb", 2, "Tuberculosis, thoracoplasty and post-TB lung disease", "6(c). Post-TB disease in 8 long cases."),
    ("ild", 2, "Interstitial and occupational lung disease", "6(b)"),
    ("pleural", 2, "Pleural effusion, pneumothorax, empyema and pleurisy", "6(c)"),
    ("hypertension", 2, "Hypertension", "6(a). Rarely asked alone, but part of many cases."),
    ("valvular-acquired", 2, "Valve disease, heart failure, cardiomyopathy, pacemaker and ICD", "6(a)"),
    ("congenital", 2, "Congenital heart disease: tetralogy of Fallot, ASD, VSD, PDA", "6(a)"),
    ("pneumonia", 3, "Pneumonia, lung abscess and atelectasis", "6(c). One ventilated long case (W24)."),
    ("paediatric", 3, "Neonatal and paediatric respiratory conditions", "6(d)"),
    ("cystic-fibrosis", 3, "Cystic fibrosis", "6(b), 6(d)"),
    ("chest-wall", 3, "Flail chest, scoliosis and kyphosis", "6(j)"),
]

# Technique cards: short pages on skills, devices, tests and scales, grouped on the home page.
CARD_GROUPS = [
    # key, title, note, home-page section
    ("icu", "ICU and ventilation", "Syllabus Ch 9, including the 9(e) conditions. Since 2023 an ICU question has appeared in every paper.", "cards"),
    ("airway", "Airway clearance", "Syllabus Ch 4(a–b).", "cards"),
    ("breathing", "Breathing and breathlessness", "Syllabus Ch 4(c–k).", "cards"),
    ("oxygen", "Oxygen, humidification and aerosols", "Syllabus Ch 4(e), 9(d).", "cards"),
    ("therapy", "Electrotherapy, therapeutic exercise and yoga", "Syllabus Ch 4(h), 4(i), 4(l).", "cards"),
    ("exercise", "Exercise testing and exercise physiology", "Syllabus Ch 2(b), 3.", "cards"),
    ("assess", "Investigations and scales", "Syllabus Ch 2(a), 10.", "cards"),
    ("rehab", "Cardiac and pulmonary rehabilitation", "Syllabus Ch 7 and 8.", "chapters"),
    ("basics", "Basics: anatomy, physiology and drugs", "Syllabus Ch 1 (revision, applied to physiotherapy).", "chapters"),
    ("emergency", "Basic life support", "Syllabus Ch 11.", "chapters"),
    ("exam", "Exam skills", "Answer writing with ICF and goals (syllabus Ch 5), and the practical exam.", "exam"),
]
CARDS = [
    # slug, group, title, meta line on the home page
    ("mechanical-ventilation", "icu", "Mechanical ventilation: indications, modes, CPAP and PEEP, complications, weaning", "In 7 papers, including a ventilated long case (S23)."),
    ("icu-physiotherapy", "icu", "Physiotherapy in the ICU: assessment, safety, equipment and ventilated cases", "In 9 papers; 4 ventilated long cases (S20, S23, S24, W24)."),
    ("suctioning", "icu", "Suctioning and manual hyperinflation", "In 7 papers; hazards of suctioning is a favourite 3-mark question."),
    ("positioning", "icu", "Therapeutic positioning, V/Q and the zones of the lung", "In 6 papers."),
    ("bed-rest", "icu", "Effects of bed rest and early mobilisation", "In 5 papers."),
    ("icu-neurological", "icu", "ICU conditions: head injury, tetanus, spinal cord injury and neuromuscular disease", "Syllabus 9(e). Not asked on their own in 2016–2026."),
    ("icu-medical", "icu", "ICU conditions: pulmonary oedema, shock, organ failure, poisoning, aspiration and drowning", "Syllabus 9(e). Not asked on their own in 2016–2026."),
    ("airway-clearance", "airway", "Airway clearance techniques: overview and choice", "Asked as a 7-mark overview in 4 papers."),
    ("acbt", "airway", "ACBT, forced expiration, huffing and autogenic drainage", "In 10 papers, the most-asked technique."),
    ("postural-drainage", "airway", "Postural drainage, percussion and vibration", "In 2 papers, and part of every airway-clearance answer."),
    ("airway-devices", "airway", "PEP, flutter, Acapella and other airway-clearance devices", "In 7 papers."),
    ("breathing-exercises", "breathing", "Breathing exercises, lung expansion and breathing retraining", "In 7 papers, counting pursed-lip breathing."),
    ("npf-pnf", "breathing", "Neurophysiological facilitation and PNF of respiration", "In 3 papers, all since 2022."),
    ("respiratory-muscle-training", "breathing", "Respiratory muscle training", "In 3 papers."),
    ("dyspnoea", "breathing", "Dyspnoea, relieving positions, energy conservation and pacing", "In 8 papers."),
    ("oxygen-therapy", "oxygen", "Oxygen therapy: devices, targets and hazards", "In 4 papers."),
    ("aerosol-humidification", "oxygen", "Humidification, nebulisers and inhalers", "In 7 papers."),
    ("electrotherapy-exercise", "therapy", "Electrotherapy and therapeutic exercise in heart, lung and vascular conditions", "Wound modalities in 4 papers."),
    ("yoga", "therapy", "Applied yoga in cardio-respiratory conditions", "Syllabus 4(l). Not asked on its own in 2016–2026."),
    ("exercise-testing", "exercise", "Exercise testing: contraindications, stop criteria, Bruce, cycle, walk and step tests", "In 9 papers."),
    ("exercise-physiology", "exercise", "Exercise physiology and prescription: METs, energy systems, intensity, training", "In 6 papers."),
    ("investigations", "assess", "Investigations: chest X-ray, PFT, ECG and bedside tests", "3-mark questions in most papers; four of the five practical spots."),
    ("scales", "assess", "Scales: Borg, mMRC, NYHA, CCS and quality-of-life questionnaires", "In 5 papers."),
    ("abg", "assess", "ABG interpretation and why patients desaturate", "In 3 papers."),
    ("breathing-patterns", "assess", "Abnormal breathing patterns and chest signs", "In 2 papers."),
    ("cardiac-rehab", "rehab", "Cardiac rehabilitation: definition, indications, contraindications, phases, outcome measures", "Part of the most-asked long answer; 7-mark questions in 5 papers."),
    ("pulmonary-rehab", "rehab", "Pulmonary rehabilitation: definition, indications, contraindications, components, outcome measures", "Long-term part of every chronic lung disease case."),
    ("respiratory-basics", "basics", "Respiratory anatomy, physiology and mechanics of the thorax", "Revision; spirogram and oxygen curve to draw."),
    ("cardiac-basics", "basics", "Cardiac anatomy and physiology for physiotherapists", "Revision; coronary territories and the conduction system."),
    ("drugs", "basics", "Cardiac and respiratory drugs: what physiotherapists need to know", "How each drug changes assessment and exercise."),
    ("bls", "emergency", "Basic life support (CPR) for physiotherapists", "Skill and viva; 2025 CPR updates."),
    ("answer-writing", "exam", "Answer writing: the paper, ICF, goals and documentation", "How to write 3-, 7- and 15-mark answers."),
    ("practical-exam", "exam", "Practical exam pack: long case, short case, spots and journal", "Follows the official 80-mark scheme."),
]

COLLECTIONS = {
    "ch6": dict(items=TOPICS, dir=("cvr", "ch6"), crumb="Chapter 6", back="All topics and cards",
                prev="Previous topic", next="Next topic"),
    "cards": dict(items=CARDS, dir=("cvr", "cards"), crumb="Technique cards", back="All topics and cards",
                  prev="Previous card", next="Next card"),
}

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
    "FiO₂": "Fraction of inspired oxygen (0.21 = room air)", "RSBI": "Rapid shallow breathing index (breathing rate ÷ tidal volume in litres)",
    "SBT": "Spontaneous breathing trial", "VAP": "Ventilator-associated pneumonia", "MHI": "Manual hyperinflation (bagging)",
    "VHI": "Ventilator hyperinflation", "ETT": "Endotracheal tube", "GBS": "Guillain–Barré syndrome",
    "RASS": "Richmond Agitation–Sedation Scale", "MAP": "Mean arterial pressure", "ICP": "Intracranial pressure",
    "PSV": "Pressure support ventilation", "HFNC": "High-flow nasal cannula", "MIP": "Maximal inspiratory pressure",
    "FRC": "Functional residual capacity", "FET": "Forced expiration technique", "TEE": "Thoracic expansion exercises",
    "MDI": "Metered-dose inhaler", "DPI": "Dry-powder inhaler", "HME": "Heat and moisture exchanger",
    "ISWT": "Incremental shuttle walk test", "ESWT": "Endurance shuttle walk test", "MET": "Metabolic equivalent",
    "CCS": "Canadian Cardiovascular Society", "SGRQ": "St George's Respiratory Questionnaire",
    "CRQ": "Chronic Respiratory Questionnaire", "CAT": "COPD Assessment Test",
    "MLHFQ": "Minnesota Living with Heart Failure Questionnaire", "KCCQ": "Kansas City Cardiomyopathy Questionnaire",
    "WIQ": "Walking Impairment Questionnaire", "NPF": "Neurophysiological facilitation of respiration",
    "PNF": "Proprioceptive neuromuscular facilitation", "RMT": "Respiratory muscle training",
    "HFCWO": "High-frequency chest wall oscillation", "VO₂max": "Maximal oxygen uptake",
    "ICU-AW": "ICU-acquired weakness",
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


def build_page(kind, slug, ready_slugs):
    coll = COLLECTIONS[kind]
    meta, body = parse_source(SRC.joinpath(*coll["dir"], f"{slug}.html"))
    body = add_abbr(body)
    up = "../../"
    toc = "\n".join(
        f'    <li><a href="#{sid}"><span class="n">{num}</span>{html.escape(label)}</a></li>'
        for sid, num, label in toc_items(body)
    )
    i = ready_slugs.index(slug)
    prev_s = ready_slugs[i - 1] if i > 0 else None
    next_s = ready_slugs[i + 1] if i + 1 < len(ready_slugs) else None
    titles = {s: t for s, _, t, _ in coll["items"]}
    nav = []
    if prev_s:
        nav.append(f'<a class="pagenav__prev" href="{prev_s}.html"><span>{coll["prev"]}</span>{html.escape(titles[prev_s])}</a>')
    if next_s:
        nav.append(f'<a class="pagenav__next" href="{next_s}.html"><span>{coll["next"]}</span>{html.escape(titles[next_s])}</a>')
    pagenav = f'  <nav class="pagenav" aria-label="Other pages">\n    {"".join(nav)}\n  </nav>\n' if nav else ""

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
    <a href="{up}index.html">{coll['back']}</a>
  </div>
</nav>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs"><a href="{up}index.html">CVR Physiotherapy</a> › {coll['crumb']} › {meta['crumb']}</p>
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
    dest = ROOT.joinpath(*coll["dir"], f"{slug}.html")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")


def build_index(ready, ready_cards):
    def row(path, is_ready, title, note):
        if is_ready:
            return (f'        <li><a class="ttl" href="{path}">{html.escape(title)}</a>'
                    f'<span class="status status--ready">Ready</span><span class="meta">{html.escape(note)}</span></li>')
        return (f'        <li><span class="ttl">{html.escape(title)}</span>'
                f'<span class="status status--soon">Coming</span><span class="meta">{html.escape(note)}</span></li>')

    tiers = {1: [], 2: [], 3: []}
    for slug, tier, title, note in TOPICS:
        tiers[tier].append(row(f"cvr/ch6/{slug}.html", slug in ready, title, note))
    done = len(ready)
    total = len(TOPICS)
    group_html = {"cards": [], "chapters": [], "exam": []}
    for key, gtitle, gnote, section in CARD_GROUPS:
        rows = [row(f"cvr/cards/{slug}.html", slug in ready_cards, title, note)
                for slug, grp, title, note in CARDS if grp == key]
        group_html[section].append(f'      <h3>{html.escape(gtitle)}</h3>\n      <p class="meta-line">{html.escape(gnote)}</p>\n'
                                   f'      <ul class="chapter-list">\n' + "\n".join(rows) + "\n      </ul>")
    cards_done = len(ready_cards)

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
      <p class="lede">The whole CVR syllabus: Chapter 6 conditions in the order they score in the real papers, technique cards for the skills, devices, tests and scales the short answers ask about, the other syllabus chapters, and exam skills. {done} of {total} topics and {cards_done} of {len(CARDS)} cards ready. Jump to the <a href="#cards">technique cards</a>, <a href="#chapters">other chapters</a> or <a href="#exam">exam skills</a>.</p>
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
        <span class="note__label">What the real paper looks like (20 papers, 2016–2026)</span>
        <p>80 marks in 3 hours. <strong>No MCQs</strong>, even though the syllabus printed a scheme with them.</p>
        <ul>
          <li>Short answers: any 5 of 6 at <strong>3 marks</strong>, and any 5 of 6 at <strong>7 marks</strong>.</li>
          <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. Every option is a patient case, and almost all start with ICF.</li>
        </ul>
        <p>Checked: Summer 2016 to Summer 2026 (20 papers; no Winter 2023 paper was available, and the Winter 2025 copy has only the short answers). The pattern has not changed. Since 2023, ventilated ICU patients appear as long cases (GBS, ARDS, pneumonia) and an ICU question appears in every paper, so study the ICU cards as closely as the Tier 1 topics.</p>
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
      <h2><span class="n">3</span>Tier 3: short notes, rarely or never asked on their own (2016–2026)</h2>
      <p>The papers say any syllabus topic can be asked, so these still get their own page.</p>
      <ul class="chapter-list">
{chr(10).join(tiers[3])}
      </ul>
    </section>

    <section class="sec" id="cards">
      <h2><span class="n">4</span>Technique cards</h2>
      <p>About 4 in 10 short-answer options test a technique, device, test or scale rather than a condition. Each card gives the principle, indications, contraindications, the procedure with doses, and the past questions.</p>
{chr(10).join(group_html["cards"])}
    </section>

    <section class="sec" id="chapters">
      <h2><span class="n">5</span>Other syllabus chapters</h2>
      <p>Rehabilitation programmes, the revision chapter and basic life support, so that every chapter of the syllabus is covered.</p>
{chr(10).join(group_html["chapters"])}
    </section>

    <section class="sec" id="exam">
      <h2><span class="n">6</span>Exam skills</h2>
{chr(10).join(group_html["exam"])}
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
    built = {}
    for kind, coll in COLLECTIONS.items():
        ready = [s for s, *_ in coll["items"] if SRC.joinpath(*coll["dir"], f"{s}.html").exists()]
        for slug in ready:
            build_page(kind, slug, ready)
        built[kind] = ready
        print(f"built {len(ready)} of {len(coll['items'])} {kind}: {', '.join(ready)}")
    build_index(set(built["ch6"]), set(built["cards"]))


if __name__ == "__main__":
    main()
