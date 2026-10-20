#!/usr/bin/env python3
"""Build the syllabus-order version of the CVR notes into cvr-syllabus/.

The topic-wise site (index.html, cvr/) orders Chapter 6 by how often each
topic is asked. This version follows the MUHS 2012 syllabus instead:
Chapters 1 to 11, then the practical list and exam skills.

Most pages are assembled from sections of the topic sources in src/cvr/, so a
fix there reaches both versions. Where one topic page covers syllabus items
that the syllabus lists apart, the split parts are hand-written fragments in
src/cvr-syllabus/ (each fragment names the topic pages it was written from).

Run from anywhere:  python3 tools/build_syllabus.py
"""
import html
import re
import sys
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  shared page frame, abbreviations, metadata parser

ROOT = build.ROOT
SRC = build.SRC
FRAG_DIR = SRC / "cvr-syllabus"
OUT = ROOT / "cvr-syllabus"
FOLDER = {p.stem: d for d in ("ch6", "cards") for p in (SRC / "cvr" / d).glob("*.html")}
SITE_NAME = "CVR by syllabus"


# ---------------------------------------------------------------- reading topic pages

class _Top(HTMLParser):
    """Find the top-level elements of an HTML fragment (start and end offsets)."""
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}

    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text, self.depth, self.start, self.items = text, 0, None, []
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]

    def _off(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            self.handle_startendtag(tag, attrs)
            return
        if self.depth == 0:
            self.start = self._off()
        self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.depth == 0:
            a = self._off()
            self.items.append((a, a + len(self.get_starttag_text())))

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        self.depth -= 1
        if self.depth == 0:
            self.items.append((self.start, self.text.index(">", self._off()) + 1))


def children(fragment):
    p = _Top(fragment)
    p.feed(fragment)
    p.close()
    return [fragment[a:b] for a, b in p.items]


def inner(element):
    return re.match(r"<(\w+)[^>]*>(.*)</\1>\s*\Z", element.strip(), re.S).group(2)


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


@lru_cache(maxsize=None)
def topic(slug):
    meta, body = build.parse_source(SRC / "cvr" / FOLDER[slug] / f"{slug}.html")
    secs, order = {}, []
    for m in re.finditer(r'<section class="sec[^"]*" id="([^"]+)"[^>]*>.*?</section>', body, re.S):
        secs[m.group(1)] = m.group(0)
        order.append(m.group(1))
    if body.count("<section") != len(order):
        sys.exit(f"{slug}: nested or unparsed sections")
    return meta, secs, order


SEC_RE = re.compile(r'<section class="(sec[^"]*)" id="([^"]+)"([^>]*)>(.*)</section>\Z', re.S)
H2_RE = re.compile(r'<h2><span class="n[^"]*">(.*?)</span>(.*?)</h2>\Z', re.S)


def parse_sec(sec_html):
    m = SEC_RE.match(sec_html.strip())
    cls, sid, attrs, body = m.groups()
    kids = children(body)
    h = H2_RE.match(kids[0])
    if not h:
        sys.exit(f"section {sid}: no numbered h2")
    toc = re.search(r'data-toc="([^"]*)"', attrs)
    return dict(sid=sid, num=h.group(1), title=h.group(2).strip(), kids=kids[1:], toc=toc.group(1) if toc else None)


def h3_text(element):
    m = re.match(r"<h3\b[^>]*>(.*?)</h3>", element, re.S)
    return plain(m.group(1)) if m else None


def groups(kids):
    """Split section children into ("pre", [...]) and one (h3 text, [...]) group per h3."""
    out = [("pre", [])]
    for k in kids:
        t = h3_text(k)
        if t is None:
            out[-1][1].append(k)
        else:
            out.append((t, [k]))
    return out


def select(kids, take, where):
    """take: None (all), ints (child positions), "pre", "h3 heading prefix", or "-prefix" to drop."""
    if take is None:
        return kids
    gs = groups(kids)

    def match(sel, key):
        return key == "pre" if sel == "pre" else key != "pre" and key.lower().startswith(sel.lower())

    if all(isinstance(t, str) and t.startswith("-") for t in take):
        drops = [t[1:] for t in take]
        for d in drops:
            if not any(match(d, key) for key, _ in gs):
                sys.exit(f"{where}: no h3 group matches '{d}'")
        return [k for key, ks in gs if not any(match(d, key) for d in drops) for k in ks]
    out = []
    for t in take:
        if isinstance(t, int):
            out.append(kids[t])
            continue
        hits = [ks for key, ks in gs if match(t, key)]
        if len(hits) != 1:
            sys.exit(f"{where}: '{t}' matches {len(hits)} h3 groups")
        out += hits[0]
    return out


def demote(h):
    for n in (5, 4, 3):
        h = re.sub(rf"<(/?)h{n}\b", rf"<\1h{n + 1}", h)
    return h


# ---------------------------------------------------------------- page building blocks

class S:
    """One section of a topic page, optionally trimmed (take), retitled or given a syllabus code."""

    def __init__(self, src, sid, title=None, code=None, take=None, prepend="", append="", dup=False, sub=(), toc=None,
                 lift=False, anchor=None):
        self.src, self.sid, self.title, self.code, self.take = src, sid, title, code, take
        self.prepend, self.append, self.dup, self.sub, self.toc = prepend, append, dup, sub, toc
        self.lift, self.anchor = lift, anchor   # lift: the first h3 of the selection becomes the section heading


class G:
    """Several topic sections joined into one section under a syllabus code; their headings drop a level."""

    def __init__(self, code, title, parts, prepend="", toc=None):
        self.code, self.title, self.parts, self.prepend, self.toc = code, title, parts, prepend, toc


class F:
    """Hand-written sections from src/cvr-syllabus/<name>.html."""

    def __init__(self, name):
        self.name = name


class X:
    """An exam corner merged from the exam corners of topic pages.

    Each part is (src, sid) or (src, sid, opts); opts: pq and qs (lists of item
    positions to keep, default all), other (True, False or a list of h3
    heading prefixes, "pre" for text before the first h3)."""

    def __init__(self, *parts, lead=""):
        self.parts, self.lead = [p if len(p) == 3 else (p[0], p[1], {}) for p in parts], lead


def ALL(src, skip=(), titles=None, codes=None, subs=None):
    _, _, order = topic(src)
    titles, codes, subs = titles or {}, codes or {}, subs or {}
    return [S(src, sid, title=titles.get(sid), code=codes.get(sid), sub=subs.get(sid, ()))
            for sid in order if sid != "sources" and sid not in skip]


class Page:
    def __init__(self, slug, code, h1, chapter, crumb, blocks, base=None, meta=None, extra_sources=()):
        self.slug, self.code, self.h1, self.chapter, self.crumb = slug, code, h1, chapter, crumb
        self.blocks, self.base, self.meta_over, self.extra_sources = blocks, base, meta or {}, extra_sources


def chips(laq=(), m7=(), m3=(), other=()):
    out = []
    for kind, label, items in (("laq", "LAQ", laq), ("7m", "7m", m7), ("3m", "3m", m3)):
        out.append("".join(f'<span class="chip chip--{kind}">{label + " " if i == 0 else ""}{s}</span>'
                           for i, s in enumerate(items)))
    out += [f'<span class="chip chip--3m">{o}</span>' for o in other]
    return " ".join(o for o in out if o)


# ---------------------------------------------------------------- the syllabus

# Chapter: (key, title, hours, items). Item: (code, syllabus wording, target or [targets], sub-items).
# Target: "page-slug" or "page-slug#id". Sub-item: (code, wording, target).
CHAPTERS = [
    ("1", "Review of basic applied anatomy and physiology", "3 hours theory", [
        ("a", "Pulmonary anatomy and physiology", "1a-pulmonary", None),
        ("b", "Cardiac anatomy and physiology", "1b-cardiac", None),
        ("c", "Cardiac and respiratory pharmacology", "1c-pharmacology", None),
        ("d", "Biomechanics of thorax (revision)", "1d-thorax", None),
    ]),
    ("2", "Investigation and exercise testing", "4 hours theory, 10 practical", [
        ("a", "Investigation and clinical implication: X-ray, PFT, ABG, ECG, ABI, claudication time, pulses, auscultation, postural hypotension", "2a-investigations", None),
        ("b", "Stress testing", "2b-stress-testing", [
            ("i", "Six-minute walk test and Harvard step test: skill and interpretation", "2b-stress-testing#s5"),
            ("ii", "Shuttle walk test and modified Bruce protocol: interpretation only", "2b-stress-testing#s4"),
        ]),
    ]),
    ("3", "Exercise physiology", "5 hours theory, 10 practical", [
        ("a", "Nutrition (bioenergetics)", "3-exercise-physiology#item-3a", None),
        ("b", "Total energy expenditure (MET) sources", "3-exercise-physiology#item-3b", None),
        ("c", "Acute and chronic adaptation to exercise", "3-exercise-physiology#item-3c", None),
        ("d", "Complications of bed rest and immobilisation, and prevention", "3-exercise-physiology#item-3d", None),
        ("e", "Aerobic and anaerobic training", "3-exercise-physiology#item-3e", None),
        ("f", "Principles of exercise prescription", "3-exercise-physiology#item-3f", None),
    ]),
    ("4", "Physiotherapy skills", "8 hours theory, 34 practical", [
        ("a", "Bronchial hygiene therapy: postural drainage, forced expiratory technique, ACBT, autogenic drainage", "4a-bronchial-hygiene", None),
        ("b", "Adjunct therapy: Flutter and PEP therapy", "4b-flutter-pep", None),
        ("c", "Therapeutic positioning to improve ventilation and perfusion matching", "4c-positioning-vq", None),
        ("d", "Therapeutic positioning to alleviate dyspnoea", "4d-positioning-dyspnoea", None),
        ("e", "Nebulisation and humidification", "4e-nebulisation-humidification", None),
        ("f", "Lung expansion therapy", "4f-lung-expansion", None),
        ("g", "Neurophysiological facilitation of respiration", "4g-npf", None),
        ("h", "Electrotherapeutic modalities for pain, swelling and wound healing", "4h-4i-electrotherapy-exercise#item-4h", None),
        ("i", "Therapeutic exercise programme to alleviate pain, achieve mobility, correct posture and improve peripheral circulation", "4h-4i-electrotherapy-exercise#item-4i", None),
        ("j", "Therapeutic exercise programme to strengthen respiratory muscles", "4j-respiratory-muscles", None),
        ("k", "Ergonomic advice, energy conservation advice, home exercise programme and modification of contextual factors", "4k-energy-conservation", None),
        ("l", "Applied yoga in cardio-respiratory conditions", "4l-yoga", None),
    ]),
    ("5", "Application of ICF model", "2 hours theory", [
        ("a", "Plan effective short-term and long-term goals to enhance functioning", "5-icf#item-5a-b", None),
        ("b", "Set patient-specific goals and expected outcome within a time frame, with clinical reasoning", "5-icf#item-5a-b", None),
        ("c", "Documentation", "5-icf#item-5c", None),
    ]),
    ("6", "Physiotherapy management", "20 hours theory, 53 practical", [
        ("a", "Medical and surgical cardiovascular diseases", None, [
            ("i", "Hypertension", "6a-i-hypertension"),
            ("ii", "IHD, myocardial infarction", "6a-ii-ihd-mi"),
            ("iii", "Valvular heart disease", "6a-iii-valvular"),
            ("iv", "Congenital", "6a-iv-congenital"),
            ("v", "Acquired", "6a-v-acquired"),
            ("vi", "Thrombosis, phlebitis and phlebothrombosis", "6a-vi-vii-venous#item-vi"),
            ("vii", "Varicose veins and ulcers", "6a-vi-vii-venous#item-vii"),
            ("viii", "Other arterial disorders", "6a-viii-arterial"),
        ]),
        ("b", "Obstructive and restrictive respiratory disorders", None, [
            ("i", "Bronchitis", "6b-i-ii-copd#item-i"),
            ("ii", "Emphysema", "6b-i-ii-copd#item-ii"),
            ("iii", "Bronchial asthma", "6b-iii-asthma"),
            ("iv", "Cystic fibrosis", "6b-iv-cystic-fibrosis"),
            ("v", "Occupational lung diseases", "6b-v-vi-ild#item-v"),
            ("vi", "Interstitial lung diseases", "6b-v-vi-ild#item-vi"),
        ]),
        ("c", "General respiratory infection", None, [
            ("i", "Tuberculosis", "6c-i-tb"),
            ("ii", "Pneumonia", "6c-ii-iii-pneumonia#item-ii"),
            ("iii", "Lung abscess", "6c-ii-iii-pneumonia#item-iii"),
            ("iv", "Bronchiectasis", "6c-iv-bronchiectasis"),
            ("v", "Pneumothorax", "6c-v-x-pleural#item-v"),
            ("vi", "Hydropneumothorax", "6c-v-x-pleural#item-vi"),
            ("vii", "Atelectasis", "6c-v-x-pleural#item-vii"),
            ("viii", "Pleuritis", "6c-v-x-pleural#item-viii"),
            ("ix", "Pleural effusion", "6c-v-x-pleural#item-ix"),
            ("x", "Empyema and other pleural disorders", "6c-v-x-pleural#item-x"),
        ]),
        ("d", "Neonatal and paediatric respiratory infection", None, [
            ("i", "ARDS", "6d-paediatric#item-i"),
            ("ii", "Meconium aspiration", "6d-paediatric#item-ii"),
            ("iii", "Pneumonitis", "6d-paediatric#item-iii-iv"),
            ("iv", "Pneumonia", "6d-paediatric#item-iii-iv"),
            ("v", "Childhood asthma", "6d-paediatric#item-v"),
            ("vi", "Cystic fibrosis and chronic lung disease", "6d-paediatric#item-vi"),
        ]),
        ("e", "Pulmonary surgeries: traumatic and surgical conditions of chest, lung, pleura and mediastinum", "6e-pulmonary-surgery", None),
        ("f", "General abdominal and oncological surgeries: pre- and post-operative care; complications and management", ["6f-abdominal-surgery", "6f-oncological-surgery"], None),
        ("g", "Burns (head, face, neck and thoracic; inhalation burns): acute care management only", "6g-burns", None),
        ("h", "Diabetic and vascular ulcers; amputations (stump care only)", ["6h-ulcers", "6h-amputation"], None),
        ("i", "Metabolic syndrome", None, [
            ("i", "Diabetes (mellitus and insipidus)", "6i-i-diabetes"),
            ("ii", "Obesity", "6i-ii-obesity"),
        ]),
        ("j", "Musculoskeletal dysfunction", None, [
            ("i", "Flail chest", "6j-musculoskeletal#item-i"),
            ("ii", "Scoliosis", "6j-musculoskeletal#item-ii"),
            ("iii", "Kyphosis", "6j-musculoskeletal#item-iii"),
        ]),
    ]),
    ("7", "Cardiac rehabilitation (AHA/ACSM guidelines)", "4 hours theory, 10 practical", [
        ("a", "Definition", "7-cardiac-rehab#s1", None),
        ("b", "Indications, contraindications", "7-cardiac-rehab#s2", None),
        ("c", "Phases (I, II, III and IV)", "7-cardiac-rehab#s5", None),
        ("d", "Outcome measures", "7-cardiac-rehab#s8", None),
    ]),
    ("8", "Pulmonary rehabilitation (AACVPR/ATS guidelines)", "2 hours theory, 5 practical", [
        ("a", "Definition", "8-pulmonary-rehab#s1", None),
        ("b", "Indications", "8-pulmonary-rehab#s2", None),
        ("c", "Contraindications", "8-pulmonary-rehab#s3", None),
        ("d", "Components of management", "8-pulmonary-rehab#s5", None),
        ("e", "Outcome measures", "8-pulmonary-rehab#s6", None),
    ]),
    ("9", "ICU evaluation and management", "8 hours theory, 12 practical", [
        ("a", "Basic evaluation", "9a-9b-evaluation-monitoring#item-9a", None),
        ("b", "Principles of ICU monitoring", "9a-9b-evaluation-monitoring#item-9b", None),
        ("c", "Mechanical ventilator modes", "9c-ventilator-modes", None),
        ("d", "Suctioning and humidification", "9d-suctioning-humidification", None),
        ("e", "Therapeutic intervention in", None, [
            ("i", "Tetanus, head injury", "9e-icu-conditions#item-i"),
            ("ii", "Pulmonary oedema", "9e-icu-conditions#item-ii"),
            ("iii", "Multiple organ failure", "9e-icu-conditions#item-iii"),
            ("iv", "Neuromuscular disease", "9e-icu-conditions#item-iv"),
            ("v", "Smoke inhalation", "9e-icu-conditions#item-v"),
            ("vi", "Poisoning", "9e-icu-conditions#item-vi"),
            ("vii", "Aspiration, near drowning", "9e-icu-conditions#item-vii"),
            ("viii", "ARDS", "9e-icu-conditions#item-viii"),
            ("ix", "Shock", "9e-icu-conditions#item-ix"),
            ("x", "Guillain–Barré syndrome", "9e-icu-conditions#item-x"),
            ("xi", "Spinal cord injury and other acute respiratory disorders", "9e-icu-conditions#item-xi"),
        ]),
    ]),
    ("10", "Introduction to functional scales", "2 hours theory, 1 practical", [
        ("a", "Generic and disease-specific", "10-functional-scales#s5", None),
        ("b", "Patient's perception of his disability and functioning, correlated with the therapist's evaluation", "10-functional-scales#s5", None),
    ]),
    ("11", "Basic life support (CPCR)", "2 hours theory, 5 practical", [
        ("", "Basic life support for physiotherapists", "11-bls", None),
    ]),
]

EXTRA_PARTS = [
    ("P", "Practical skills (the syllabus practical list)", "Inside the 140 practical hours", [
        ("1–10", "The ten practical skills, with handling skills and equipment", "practical-skills", None),
    ]),
    ("E", "Exam skills", "How the notes become marks", [
        ("", "Answer writing for the theory paper", "exam-theory", None),
        ("", "The practical exam: long case, short case, spots and journal", "exam-practical", None),
    ]),
]

CHAPTER_TITLES = {c[0]: c[1] for c in CHAPTERS + EXTRA_PARTS}


def crumb_for(chapter):
    if chapter == "P":
        return "Practical skills"
    if chapter == "E":
        return "Exam skills"
    return f"Chapter {chapter}: {CHAPTER_TITLES[chapter]}"


RB, EP, BR, VA, VEN, PL = "respiratory-basics", "exercise-physiology", "bed-rest", "valvular-acquired", "venous", "pleural"

# Definitions for the two venous items, split from the shared definition list in ch6/venous.html (section 1).
VENOUS_VI_DEFS = """<h3>Definitions</h3>
    <ul>
      <li><strong>Thrombosis:</strong> a blood clot forming inside a vessel. <strong>Deep vein thrombosis (DVT):</strong> a clot in a deep vein, usually of the calf or thigh. Part of it can break off and block the lung arteries: <strong>pulmonary embolism (PE)</strong>. DVT and PE together are called venous thromboembolism.</li>
      <li><strong>Phlebitis:</strong> inflammation of a vein. <strong>Thrombophlebitis</strong> (superficial): inflammation of a superficial vein with a clot in it; a red, tender cord under the skin.</li>
      <li><strong>Phlebothrombosis:</strong> the older term for a clot in a deep vein with little inflammation, so it is often silent.</li>
    </ul>"""
VENOUS_VII_DEFS = """<h3>Definitions</h3>
    <ul>
      <li><strong>Varicose veins:</strong> dilated, twisted superficial veins of the legs, 3 mm or more in diameter when standing, caused by faulty valves.</li>
      <li><strong>Chronic venous insufficiency:</strong> long-term high pressure in the leg veins (venous hypertension) causing swelling, skin changes and ulcers.</li>
      <li><strong>Venous ulcer:</strong> a break in the skin of the lower leg, usually above the inner ankle, caused by venous hypertension, that has not healed within about 2 weeks.</li>
    </ul>"""

PAGES = [
    # ---------- Chapter 1
    Page("1a-pulmonary", "1(a)", "Pulmonary anatomy and physiology", "1", None,
         [S(RB, "s1"), S(RB, "s3"), S(RB, "s4"), S(RB, "s5"), S(RB, "s6"),
          X((RB, "s7", dict(qs=[1, 2])))],
         base=RB,
         meta=dict(syllabus="Ch 1(a) Pulmonary anatomy and physiology (revision, applied to physiotherapy)",
                   lede="Chapter 1 is revision of earlier years, applied to physiotherapy. It is rarely asked on its own, but every technique answer rests on it: why a breath hold reopens alveoli, why huffing clears small airways, why the oxygen curve matters in a desaturating patient. Learn the numbers and the drawings that turn up again and again.")),
    Page("1b-cardiac", "1(b)", "Cardiac anatomy and physiology", "1", None, ALL("cardiac-basics"), base="cardiac-basics",
         meta=dict(syllabus="Ch 1(b) Cardiac anatomy and physiology")),
    Page("1c-pharmacology", "1(c)", "Cardiac and respiratory pharmacology", "1", None, ALL("drugs"), base="drugs",
         meta=dict(syllabus="Ch 1(c) Cardiac and respiratory pharmacology")),
    Page("1d-thorax", "1(d)", "Biomechanics of the thorax (revision)", "1", None,
         [S(RB, "s2"), X((RB, "s7", dict(other=False, qs=[0], dup=True)))],
         base=RB,
         meta=dict(syllabus="Ch 1(d) Biomechanics of thorax (revision)",
                   lede="How the ribs, diaphragm and accessory muscles move air, revised for physiotherapy. It explains why a flattened diaphragm fails in COPD, why posture changes breathing, and why some positions make breathing easier.")),

    # ---------- Chapter 2
    Page("2a-investigations", "2(a)", "Investigations and their clinical implication", "2", None,
         [S("investigations", "s1"), S("investigations", "s2"),
          S("abg", "s1", title="Arterial blood gas: normal values"),
          S("abg", "s2", title="Arterial blood gas: four steps to interpret"),
          S("abg", "s3", title="Arterial blood gas: causes of each disorder (3 marks in S24)"),
          S("abg", "s4", title="Arterial blood gas: oxygenation and respiratory failure"),
          S("abg", "s5", title="Why patients desaturate on exercise (3 marks in S21)"),
          S("abg", "s6", title="What the arterial blood gas means for physiotherapy"),
          S("investigations", "s3"),
          S("investigations", "s4", title="Bedside cardiovascular tests: pulses, postural hypotension, ABI, claudication time"),
          S("breathing-patterns", "s2", title="Auscultation and chest signs"),
          S("breathing-patterns", "s1"),
          X(("investigations", "s5"), ("abg", "s7"), ("breathing-patterns", "s3"))],
         base="investigations",
         meta=dict(syllabus="Ch 2(a) Investigation and clinical implication: X-ray, PFT, ABG, ECG, ABI, claudication time, pulses, auscultation, postural hypotension",
                   priority='<span class="tier">High yield.</span> 3-mark questions in most papers (X-ray, PFT, ECG, ABG, ABI, breathing patterns), and four of the five practical spots.',
                   asked=chips(m7=["W24 (ABG, PFT, X-ray in COPD)"], m3=["S16 ×2", "W18", "S19", "W19", "W20", "S21 ×2", "S22", "S24 ×2"]),
                   split="3-mark findings and causes; part of COPD and ICU long answers; practical spots",
                   checked="ERS/ATS interpretive strategies for lung function tests (2022); Fourth Universal Definition of MI (2018); consensus definition of orthostatic hypotension (2011); BTS emergency oxygen guideline (2017); standard acid–base physiology. Full list under Sources.",
                   lede="Investigations are asked as 3-mark questions in most papers: X-ray of effusion, emphysema and tetralogy of Fallot, PFT in obstructive and restrictive disease, ECG criteria for MI, ABG causes and desaturation, ABI and breathing patterns. They are also four of the five practical spots. Learn a fixed order for reading each test and what the result changes in physiotherapy.")),
    Page("2b-stress-testing", "2(b)", "Stress testing: walk tests, step test, shuttle test and Bruce protocol", "2", None,
         ALL("exercise-testing"), base="exercise-testing",
         meta=dict(syllabus="Ch 2(b) Stress testing: (i) 6-minute walk test and Harvard step test, skill and interpretation; (ii) shuttle walk test and modified Bruce protocol, interpretation only")),

    # ---------- Chapter 3
    Page("3-exercise-physiology", "3(a)–(f)", "Exercise physiology", "3", None,
         [S(EP, "s2", code="3(a)", title="Nutrition (bioenergetics): the energy systems (7 marks in S24)"),
          S(EP, "s1", code="3(b)", title="Total energy expenditure: the MET (3 marks in W22, S24, S25)"),
          S(EP, "s5", code="3(c)", title="Acute and chronic adaptations to exercise", take=[1]),
          G("3(d)", "Complications of bed rest and immobilisation, and prevention",
            [S(BR, "s1"), S(BR, "s2"), S(BR, "s3"), S(BR, "s4")]),
          S(EP, "s3", code="3(e)", title="Aerobic and anaerobic training (3 marks in W22)"),
          G("3(f)", "Principles of exercise prescription",
            [S(EP, "s5", title="Principles of training: FITT-VP", take=[0], dup=True), S(EP, "s4"), S(EP, "s6")]),
          X((EP, "s7"), (BR, "s5"))],
         base=EP,
         meta=dict(syllabus="Ch 3 Exercise physiology: (a) nutrition (bioenergetics); (b) total energy expenditure (MET) sources; (c) acute and chronic adaptation to exercise; (d) complications of bed rest and immobilisation, and prevention; (e) aerobic and anaerobic training; (f) principles of exercise prescription",
                   priority='<span class="tier">High yield.</span> In 10 of 20 papers (2016–2026): bed rest in 5, the rest in 6.',
                   asked=chips(m7=["S16", "W17", "S23", "S24 ×2", "S26"], m3=["S19", "W21", "W22 ×2", "S24", "S25", "W25"]),
                   split="3-mark MET, Karvonen, aerobic vs anaerobic, effects of bed rest; 7-mark energy systems, intensity, ageing, bed rest by system",
                   checked="2024 Adult Compendium of Physical Activities (MET values); ACSM intensity classification; WHO physical activity guidelines (2020); Dallas bed rest study (1968); ICU-acquired weakness definition (2002). Full list under Sources.",
                   lede="Exercise physiology appears as 3-mark definitions (MET, aerobic vs anaerobic, Karvonen) and 7-mark explanations (energy systems, measuring intensity, ageing). Bed rest, 3(d), was asked five times. These numbers also run through every cardiac and pulmonary rehabilitation answer.")),

    # ---------- Chapter 4
    Page("4a-bronchial-hygiene", "4(a)", "Bronchial hygiene therapy: postural drainage, forced expiration technique, ACBT, autogenic drainage", "4", None,
         [S("airway-clearance", "s1"), S("airway-clearance", "s2", title="Classification of airway clearance techniques"),
          S("airway-clearance", "s6"), S("airway-clearance", "s3", title="Airway clearance techniques: application, advantages and disadvantages (S19, W24)"),
          S("airway-clearance", "s4"), S("airway-clearance", "s5"),
          S("postural-drainage", "s1", title="Postural drainage: what it is"),
          S("postural-drainage", "s2", title="Postural drainage: positions for each lobe"),
          S("postural-drainage", "s3", title="Postural drainage: indications"),
          S("postural-drainage", "s4", title="Postural drainage: contraindications (3 marks in S18)"),
          S("postural-drainage", "s5"),
          S("acbt", "s1"), S("acbt", "s2", title="ACBT components and the forced expiration technique: physiological principle (S23)"),
          S("acbt", "s3", title="ACBT: indications and contraindications"), S("acbt", "s4", title="ACBT: procedure and dose"),
          S("acbt", "s5"), S("acbt", "s6"),
          X(("airway-clearance", "s7"), ("postural-drainage", "s6"), ("acbt", "s7"))],
         base="acbt",
         meta=dict(syllabus="Ch 4(a) Bronchial hygiene therapy: postural drainage, forced expiratory technique, ACBT, autogenic drainage",
                   priority='<span class="tier">High yield.</span> In 13 of 20 papers (2016–2026); ACBT is the most-asked technique.',
                   asked=chips(m7=["W16", "S17", "W17", "W18 (neonate)", "S19", "W19", "S20", "S23", "W24", "S26"], m3=["W16", "W17", "S18", "S19", "W19", "S20", "W20", "W25"]),
                   split="7-mark ACBT, autogenic drainage or an overview of techniques; 3-mark components, huff vs cough, phases, contraindications",
                   checked="BTS/ACPRC physiotherapy guideline (2009); ERS bronchiectasis guideline (2025); Cystic Fibrosis Trust physiotherapy standards (2026); classic descriptions of ACBT (Pryor) and autogenic drainage (Chevaillier). Full list under Sources.",
                   lede="Bronchial hygiene is the most-asked skill in this paper: ACBT as 7 marks in W16, S23 and S26, its parts, huffing, FET and autogenic drainage as 3 marks, the overview of techniques (S19, W24), mucus removal (W19) and postural drainage contraindications (S18). Learn the overview first, then each technique with its principle, dose and contraindications.")),
    Page("4b-flutter-pep", "4(b)", "Adjunct therapy: Flutter and PEP therapy", "4", None, ALL("airway-devices"), base="airway-devices",
         meta=dict(syllabus="Ch 4(b) Adjunct therapy: Flutter and PEP therapy; practical: mechanical assistive devices (PEP, Flutter, vest)")),
    Page("4c-positioning-vq", "4(c)", "Therapeutic positioning to improve ventilation and perfusion matching", "4", None,
         [S("positioning", s) for s in ("s1", "s2", "s3", "s4", "s5")] + [S("positioning", "s7")],
         base="positioning",
         meta=dict(syllabus="Ch 4(c) Therapeutic positioning to improve ventilation and perfusion matching")),
    Page("4d-positioning-dyspnoea", "4(d)", "Therapeutic positioning to alleviate dyspnoea", "4", None,
         [S("dyspnoea", "s1", title="Dyspnoea: definition"), S("dyspnoea", "s2"), S("dyspnoea", "s3"), S("dyspnoea", "s4"),
          X(("dyspnoea", "s7", dict(pq=[], other=["Answer skeleton"], qs=[0, 2])),
            lead='<h3>Past questions (MUHS, 2016–2026)</h3><ul class="pq">'
                 '<li><span class="src">W25 Q2(a), 7 marks</span>Define dyspnoea, explain the mechanism of its perception and its treatment.</li>'
                 '<li><span class="src">S22 Q1(e), 3 marks</span>Rationale of therapeutic positioning to alleviate dyspnoea.</li></ul>'
                 '<p>Energy conservation and pacing questions are in <a href="4k-energy-conservation.html">4(k)</a>.</p>')],
         base="dyspnoea",
         meta=dict(syllabus="Ch 4(d) Therapeutic positioning to alleviate dyspnoea",
                   priority='<span class="tier">High yield.</span> Dyspnoea questions are in 8 of 20 papers (2016–2026); this part was asked as 7 marks in W25 and 3 marks in S22.',
                   asked=chips(m7=["W25"], m3=["S22"]),
                   split="7-mark dyspnoea: definition, mechanism, treatment; 3-mark rationale of positioning",
                   lede="Breathlessness was asked as its definition, mechanism of perception and treatment (W25) and as the rationale of positions that ease it (S22). Learn how breathlessness is perceived first; the positions and the treatment follow from it. Energy conservation and pacing are in 4(k).")),
    Page("4e-nebulisation-humidification", "4(e)", "Nebulisation and humidification, with oxygen therapy", "4", None,
         ALL("aerosol-humidification", skip=("s5",)) +
         [S("oxygen-therapy", "s1", title="Oxygen therapy (practical list, item 2): what oxygen is for"),
          S("oxygen-therapy", "s2", title="Oxygen therapy: methods of delivery (3 marks in S23)"),
          S("oxygen-therapy", "s3"), S("oxygen-therapy", "s4"),
          S("oxygen-therapy", "s5", title="Oxygen therapy: the physiotherapist's role"),
          X(("aerosol-humidification", "s5"), ("oxygen-therapy", "s6"))],
         base="aerosol-humidification",
         meta=dict(syllabus="Ch 4(e) Nebulisation and humidification; practical: medication delivery, e.g. nebulisation, oxygen",
                   priority='<span class="tier">High yield.</span> In 10 of 20 papers (2016–2026): humidification and nebulisers in 7, oxygen in 4.',
                   asked=chips(m7=["S20 ×2", "S24"], m3=["S17", "W17", "S19", "S21", "S23", "S25", "W25 ×2"]),
                   split="3-mark definitions, uses, inhalers, oxygen delivery or hazards; 7-mark nebuliser types or low-flow oxygen",
                   checked="AARC humidification guideline (2012); BTS guideline for oxygen use (2017, with later updates); ATS home oxygen guideline (2020); Cochrane review of spacers versus nebulisers (2013). Full list under Sources.",
                   lede="Seven papers asked humidification and nebulisers (definitions, uses, jet and ultrasonic nebulisers, indications and types, inhalers) and four asked oxygen (low-flow oxygen, delivery methods, hazards, hypoxic drive). Oxygen is not a separate syllabus chapter; it sits here because the practical list puts it with nebulisation under medication delivery.")),
    Page("4f-lung-expansion", "4(f)", "Lung expansion therapy and breathing exercises", "4", None, ALL("breathing-exercises"), base="breathing-exercises",
         meta=dict(syllabus="Ch 4(f) Lung expansion therapy; practical: breathing control strategies (pursed-lip breathing, sustained maximal inspiration, deep breathing)")),
    Page("4g-npf", "4(g)", "Neurophysiological facilitation of respiration, with PNF", "4", None, ALL("npf-pnf"), base="npf-pnf",
         meta=dict(syllabus="Ch 4(g) Neurophysiologic facilitation of respiration; practical: PNF for breathing facilitation and inhibition")),
    Page("4h-4i-electrotherapy-exercise", "4(h)–(i)", "Electrotherapy for pain, swelling and wound healing; therapeutic exercise", "4", None,
         [G("4(h)", "Electrotherapeutic modalities for pain, swelling and wound healing",
            [S("electrotherapy-exercise", s) for s in ("s1", "s2", "s3", "s4", "s5")]),
          S("electrotherapy-exercise", "s6", code="4(i)", title="Therapeutic exercise programmes: pain, mobility, posture and peripheral circulation"),
          S("electrotherapy-exercise", "s7")],
         base="electrotherapy-exercise",
         meta=dict(syllabus="Ch 4(h) Electrotherapeutic modalities for pain, swelling and wound healing; 4(i) Therapeutic exercise programme to alleviate pain, achieve mobility, correct posture and improve peripheral circulation")),
    Page("4j-respiratory-muscles", "4(j)", "Therapeutic exercise programme to strengthen the respiratory muscles", "4", None,
         ALL("respiratory-muscle-training"), base="respiratory-muscle-training",
         meta=dict(syllabus="Ch 4(j) Therapeutic exercise program to strengthen respiratory muscles; practical: ventilatory muscle training")),
    Page("4k-energy-conservation", "4(k)", "Ergonomic and energy-conservation advice, home programmes and contextual factors", "4", None,
         [S("dyspnoea", "s5"), S("dyspnoea", "s6"),
          S("bronchiectasis", "s12", take=["Ergonomic"], dup=True, title="Ergonomic advice: a worked example (W22)",
            prepend='<p>From the bronchiectasis notes (<a href="../ch6/bronchiectasis.html#s12">6(c)(iv)</a>), where this question was asked.</p>'),
          F("4k-home"),
          S("handling-skills", "s7"),
          X(("dyspnoea", "s7", dict(pq=[], other=False, qs=[1], dup=True)),
            lead='<h3>Past questions (MUHS, 2016–2026)</h3><ul class="pq">'
                 '<li><span class="src">7-mark questions</span>Energy conservation techniques for COPD and their importance (S19; see <a href="../ch6/copd.html#s12">6(b)(i–ii)</a>). Methods of energy conservation (S22). Ergonomic and energy-conservation advice in left lung bronchiectasis (W22).</li>'
                 '<li><span class="src">3-mark questions</span>Three energy conservation techniques for a breathless patient (W17). Pacing of activities in a breathless patient (S20). Activity pacing with examples (W21). Energy conservation techniques (S25).</li></ul>')],
         base="dyspnoea",
         meta=dict(syllabus="Ch 4(k) Deliver ergonomic advice, energy conservation advice, home exercise program and modifications of contextual factors",
                   priority='<span class="tier">High yield.</span> Energy conservation and pacing were asked in 7 of 20 papers (2016–2026).',
                   asked=chips(m7=["S19", "S22", "W22"], m3=["W17", "S20", "W21", "S25"]),
                   split="7-mark energy conservation or ergonomic advice; 3-mark techniques or pacing with examples",
                   lede="Energy conservation was asked as 7 marks (S19, S22, and as ergonomic advice in left lung bronchiectasis, W22) and as 3 marks (W17, S25), and pacing twice (S20, W21). Every condition page ends with its own home programme; this page gathers the general advice and links to each programme.")),
    Page("4l-yoga", "4(l)", "Applied yoga in cardio-respiratory conditions", "4", None, ALL("yoga"), base="yoga",
         meta=dict(syllabus="Ch 4(l) Applied yoga in cardio-respiratory conditions; practical: relaxation training")),

    # ---------- Chapter 5
    Page("5-icf", "5", "Application of the ICF model: goals and documentation", "5", None,
         [S("answer-writing", "s4", code="ICF", title="Applying the ICF model"),
          S("answer-writing", "s5", code="5(a–b)", title="Short-term and long-term goals with time frames"),
          S("answer-writing", "s6", code="5(c)", title="Documentation: SOAP notes")],
         base="answer-writing",
         meta=dict(syllabus="Ch 5 Application of ICF model: (a) short-term and long-term goals; (b) patient-specific goals and expected outcome within a time frame, with clinical reasoning; (c) documentation",
                   lede="Almost every long answer in the 20 papers (2016–2026) starts with ICF, a functional diagnosis or impairments, then goals. This chapter is short in the syllabus but earns marks in every case. Most Chapter 6 pages have a worked ICF example from a real paper, in their \"PT diagnosis by ICF\" section.")),

    # ---------- Chapter 6
    Page("6a-i-hypertension", "6(a)(i)", "Hypertension", "6", "6(a) Medical and surgical cardiovascular diseases", ALL("hypertension"), base="hypertension"),
    Page("6a-ii-ihd-mi", "6(a)(ii)", "IHD, myocardial infarction, angioplasty and CABG", "6", "6(a) Medical and surgical cardiovascular diseases", ALL("ihd-mi-cabg"), base="ihd-mi-cabg"),
    Page("6a-iii-valvular", "6(a)(iii)", "Valvular heart disease", "6", "6(a) Medical and surgical cardiovascular diseases",
         [F("6a-iii-a"),
          S(VA, "s2", take=["Valve lesions"], lift=True, dup=True),
          F("6a-iii-b"),
          S(VA, "s12", take=["Cardiac rehab after valve"], lift=True, dup=True, anchor="rehab",
            title="Cardiac rehabilitation after valve replacement (7 marks in W21)"),
          F("6a-iii-c")],
         base="valvular-acquired",
         meta=dict(syllabus="Ch 6(a)(iii) Valvular heart disease",
                   priority='<span class="tier">Tier 2.</span> A 7-mark question on cardiac rehabilitation after valve replacement (W21).',
                   asked=chips(m7=["W21 (valve replacement)"]),
                   split="7-mark rehabilitation after valve replacement (Phases 1 and 2)",
                   lede="Valve disease was asked as cardiac rehabilitation after valve replacement (W21, 7 marks). Learn the four common valve lesions with their murmurs, why rheumatic heart disease still matters in India, which lesion makes exercise unsafe, and Phases 1 and 2 after valve surgery.")),
    Page("6a-iv-congenital", "6(a)(iv)", "Congenital heart disease", "6", "6(a) Medical and surgical cardiovascular diseases", ALL("congenital"), base="congenital"),
    Page("6a-v-acquired", "6(a)(v)", "Acquired heart disease: heart failure, cardiomyopathy, pacemakers and ICDs", "6", "6(a) Medical and surgical cardiovascular diseases",
         [F("6a-v-a"),
          S(VA, "s2", take=["Heart failure by", "NYHA"], title="Classification: ejection fraction and NYHA classes (3 marks in S21)"),
          F("6a-v-b"), S(VA, "s4"), F("6a-v-c"),
          S(VA, "s9"), S(VA, "s10"), S(VA, "s11"),
          S(VA, "s12", take=["Pre-implantation", "Post-implantation", "Exercise training", "If the ICD"], title="PT management"),
          S(VA, "s13"), S(VA, "s14"), S(VA, "s15"),
          X((VA, "s16", dict(pq=[0, 1, 3], qs=[0, 1, 2])))],
         base="valvular-acquired",
         meta=dict(syllabus="Ch 6(a)(v) Acquired heart disease: heart failure, cardiomyopathy, pacemakers and ICDs",
                   priority='<span class="tier">Tier 2.</span> 1 long-answer case (S22: pacemaker and ICD in cardiomyopathy) and a 3-mark question (S21, NYHA); heart failure appears inside cardiac cases (S20, EF 25%; S25, EF 40%).',
                   asked=chips(laq=["S22"], m3=["S21 (NYHA)"]),
                   split="15 (pre- and post-implantation assessment and management); 3-mark NYHA grades",
                   lede="A 2022 long answer asked for pre- and post-implantation physiotherapy for a teacher with cardiomyopathy getting a pacemaker and ICD, and NYHA grades were asked as 3 marks (S21). Heart failure also sits inside cardiac cases (S20, EF 25%; S25, EF 40%). Learn heart failure by ejection fraction, safe exercise training for a weak heart, and the device precautions.")),
    Page("6a-vi-vii-venous", "6(a)(vi)–(vii)", "Thrombosis, phlebitis and phlebothrombosis; varicose veins and ulcers", "6", "6(a) Medical and surgical cardiovascular diseases",
         [G("vi", "Thrombosis, phlebitis and phlebothrombosis",
            [S(VEN, "s2", take=["DVT by site"], lift=True, title="Types: DVT by site", dup=True),
             S(VEN, "s3", take=["DVT: Virchow"], lift=True, title="Causes: Virchow's triad", dup=True),
             S(VEN, "s5", take=["DVT", "Superficial thrombophlebitis"], title="Clinical features", dup=True),
             S(VEN, "s6", take=["DVT diagnosis"], lift=True, title="Investigations: diagnosing DVT", dup=True),
             S(VEN, "s7", take=["DVT", "Superficial thrombophlebitis"], title="Medical management", dup=True),
             S(VEN, "s12", take=["3. DVT"], lift=True, dup=True,
               title="Physiotherapy: DVT prevention and management (7 marks in S18, W18, S22)")],
            prepend=VENOUS_VI_DEFS),
          G("vii", "Varicose veins and ulcers",
            [S(VEN, "s2", take=["CEAP"], lift=True, title="Classification: CEAP clinical classes (2020)"),
             S(VEN, "s3", take=["Varicose veins"], lift=True, title="Causes and risk factors"),
             S(VEN, "s4", title="Pathophysiology: the calf muscle pump and how an ulcer forms"),
             S(VEN, "s5", take=["Varicose veins", "Don't confuse"], title="Clinical features"),
             S(VEN, "s6", take=["pre"], title="Special tests and investigations (3 marks in S16)"),
             S(VEN, "s7", take=["Varicose veins", "Venous ulcer"], title="Medical and surgical management"),
             S(VEN, "s12", take=["1. Varicose", "2. Venous ulcer"], title="Physiotherapy (venous ulcer: 7 marks in W16, W20, W21)")],
            prepend=VENOUS_VII_DEFS),
          S(VEN, "s8"), S(VEN, "s9"), S(VEN, "s10"), S(VEN, "s11"),
          S(VEN, "s12", take=["By impairment"], lift=True, title="Treatment by impairment", dup=True),
          S(VEN, "s13"), S(VEN, "s14"), S(VEN, "s15"),
          S(VEN, "s16", sub=(("Virchow's triad (section 3)", "Virchow's triad (vi above)"),
                             ("The leg-ulcer comparison table (section 5)", "The leg-ulcer comparison table (vii above)")))],
         base="venous",
         meta=dict(syllabus="Ch 6(a)(vi) Thrombosis, phlebitis and phlebothrombosis; 6(a)(vii) Varicose veins and ulcers")),
    Page("6a-viii-arterial", "6(a)(viii)", "Other arterial disorders: peripheral arterial disease, Buerger's disease and others", "6", "6(a) Medical and surgical cardiovascular diseases",
         ALL("pad"), base="pad"),
    Page("6b-i-ii-copd", "6(b)(i)–(ii)", "Bronchitis and emphysema (COPD)", "6", "6(b) Obstructive and restrictive respiratory disorders",
         [F("6b-i-ii-intro")] + ALL("copd"), base="copd",
         meta=dict(syllabus="Ch 6(b)(i) Bronchitis; 6(b)(ii) Emphysema; pulmonary rehabilitation from Ch 8")),
    Page("6b-iii-asthma", "6(b)(iii)", "Bronchial asthma", "6", "6(b) Obstructive and restrictive respiratory disorders", ALL("asthma"), base="asthma"),
    Page("6b-iv-cystic-fibrosis", "6(b)(iv)", "Cystic fibrosis", "6", "6(b) Obstructive and restrictive respiratory disorders", ALL("cystic-fibrosis"), base="cystic-fibrosis"),
    Page("6b-v-vi-ild", "6(b)(v)–(vi)", "Occupational and interstitial lung diseases", "6", "6(b) Obstructive and restrictive respiratory disorders",
         [F("6b-v-vi-intro")] + ALL("ild"), base="ild"),
    Page("6c-i-tb", "6(c)(i)", "Tuberculosis", "6", "6(c) General respiratory infection", ALL("tb"), base="tb"),
    Page("6c-ii-iii-pneumonia", "6(c)(ii)–(iii)", "Pneumonia and lung abscess", "6", "6(c) General respiratory infection",
         [S("pneumonia", "s1", code="ii"), S("pneumonia", "s2", code="iii"),
          X(("pneumonia", "s4", dict(qs=[0, 1], sub=(("Worked plan in section 1.", "Worked plan in ii above."),))))],
         base="pneumonia",
         meta=dict(syllabus="Ch 6(c)(ii) Pneumonia; 6(c)(iii) Lung abscess",
                   lede="Pneumonia came as a ventilated long case (W24) and inside COPD and ICU cases; lung abscess has not been asked on its own. For each, learn what it is, the medical point that changes physiotherapy, and the treatment by problem. Atelectasis, 6(c)(vii), is with the pleural disorders.")),
    Page("6c-iv-bronchiectasis", "6(c)(iv)", "Bronchiectasis", "6", "6(c) General respiratory infection", ALL("bronchiectasis"), base="bronchiectasis"),
    Page("6c-v-x-pleural", "6(c)(v)–(x)", "Pneumothorax, hydropneumothorax, atelectasis, pleuritis, pleural effusion and empyema", "6", "6(c) General respiratory infection",
         [F("6c-v-vi"), S("pneumonia", "s3", code="vii"), F("6c-viii-x"),
          S(PL, "s3", title="Pathophysiology to impairments: all pleural disorders"),
          S(PL, "s7"), S(PL, "s8"),
          S(PL, "s9", title="PT diagnosis by ICF: worked empyema case (S25)"),
          S(PL, "s10"), S(PL, "s14"), S(PL, "s15"),
          X((PL, "s16", dict(sub=(("See the worked example in section 9.", "See the worked example on this page."),))),
            ("pneumonia", "s4", dict(pq=[], other=False, qs=[2], dup=True)))],
         base="pleural",
         meta=dict(syllabus="Ch 6(c)(v) Pneumothorax; (vi) hydropneumothorax; (vii) atelectasis; (viii) pleuritis; (ix) pleural effusion; (x) empyema and other pleural disorders")),
    Page("6d-paediatric", "6(d)", "Neonatal and paediatric respiratory conditions", "6", None,
         [S("paediatric", "s1", code="•"),
          G("i", "ARDS: neonatal respiratory distress syndrome and paediatric ARDS", [S("paediatric", "s2"), S("paediatric", "s6")]),
          S("paediatric", "s3", code="ii"),
          S("paediatric", "s4", code="iii–iv", title="Pneumonitis and pneumonia in children"),
          S("asthma", "s12", code="v", title="Childhood asthma", take=["3. Paediatric", "Parent and teacher"], dup=True,
            sub=(("3. Paediatric asthma rehabilitation", "Paediatric asthma rehabilitation"),),
            prepend='<p>Asthma itself (causes, attacks, drugs, assessment) is in <a href="../ch6/asthma.html">6(b)(iii)</a>. These are the parts of that page written for children.</p>'),
          G("vi", "Cystic fibrosis and chronic lung disease", [S("paediatric", "s5")],
            prepend='<p>Cystic fibrosis has its own page, <a href="../ch6/cystic-fibrosis.html">6(b)(iv)</a>: daily airway clearance starts from diagnosis in infancy and becomes play-based PEP and exercise in childhood. Chronic lung disease of prematurity is below.</p>'),
          S("paediatric", "s8", sub=(("(section 4).", "(iii–iv above)."),))],
         base="paediatric",
         meta=dict(syllabus="Ch 6(d) Neonatal and paediatric respiratory infection: (i) ARDS, (ii) meconium aspiration, (iii) pneumonitis, (iv) pneumonia, (v) childhood asthma, (vi) cystic fibrosis and chronic lung disease")),
    Page("6e-pulmonary-surgery", "6(e)", "Pulmonary surgeries and chest trauma", "6", None, ALL("lung-surgery"), base="lung-surgery"),
    Page("6f-abdominal-surgery", "6(f)", "General abdominal surgery: pre- and post-operative care, complications", "6", "6(f) General abdominal and oncological surgeries",
         ALL("abdominal-surgery"), base="abdominal-surgery"),
    Page("6f-oncological-surgery", "6(f)", "Oncological surgery: mastectomy and lymphoedema", "6", "6(f) General abdominal and oncological surgeries",
         ALL("mastectomy"), base="mastectomy"),
    Page("6g-burns", "6(g)", "Burns: acute care, positioning, splinting and inhalation injury", "6", None, ALL("burns"), base="burns"),
    Page("6h-ulcers", "6(h)", "Diabetic and vascular ulcers", "6", "6(h) Diabetic and vascular ulcers; amputations",
         [F("6h-intro"),
          S("diabetes", "s2", title="Diabetic foot: Wagner grades and risk categories", take=["Diabetic foot", "Foot risk"], dup=True),
          S("diabetes", "s4", title="Why the diabetic foot ulcerates", take=["Why the diabetic foot"], dup=True),
          S("venous", "s5", title="Three kinds of leg ulcer", take=["Don't confuse"], dup=True),
          S("diabetes", "s4", title="Wound healing: stages and factors", take=["Stages of wound", "Factors affecting"], dup=True,
            sub=(("the modalities in section 12", "the modalities in the electrotherapy section below"),)),
          S("diabetes", "s12", title="Diabetic foot care (7 marks in S19)", take=["Diabetic foot care"], dup=True),
          S("diabetes", "s12", title="Electrotherapy for wound healing", take=["Electrotherapy for wound"], dup=True),
          S("diabetes", "s12", title="Pressure sores (pressure injuries)", take=["Pressure sores"], dup=True),
          X(("diabetes", "s16", dict(pq=[], other=False, qs=[1, 3], dup=True)),
            ("venous", "s16", dict(pq=[], other=False, qs=[2, 4], dup=True)),
            lead='<h3>Past questions (MUHS, 2016–2026)</h3><ul class="pq">'
                 '<li><span class="src">7-mark questions</span>What is diabetic foot, how to care for it, and why (S19). Physiotherapy for pressure sores (W19). Modalities for wound healing (S24). Factors affecting wound healing, with the modalities used (S25).</li>'
                 '<li><span class="src">3-mark questions</span>Three electrotherapy modalities for an infected wound (S16). Stages of wound healing (S19). Three electrotherapy modalities with parameters for wound healing (S22).</li>'
                 '<li><span class="src">Related</span>Venous ulcers (7 marks in W16, W20 and W21) are with varicose veins in <a href="../ch6/venous.html#s12">6(a)(vii)</a>.</li></ul>')],
         base="diabetes",
         meta=dict(syllabus="Ch 6(h) Diabetic and vascular ulcers",
                   priority='<span class="tier">Tier 2.</span> Diabetic foot, wound healing and pressure sores together in 7 of 20 papers (2016–2026).',
                   asked=chips(m7=["S19", "W19", "S24", "S25"], m3=["S16", "S19", "S22"]),
                   split="7-mark diabetic foot, pressure sores or wound-healing modalities; 3-mark stages of wound healing or modalities",
                   lede="Ulcers were asked as diabetic foot care (S19), pressure sores (W19), wound-healing stages and factors (S19, S25) and wound-healing modalities (S16, S22, S24). Learn the three kinds of leg ulcer, why the diabetic foot breaks down, and how physiotherapy helps a wound heal. Venous and arterial ulcers are treated with their vessels in 6(a)(vii) and 6(a)(viii).")),
    Page("6h-amputation", "6(h)", "Amputation and stump care", "6", "6(h) Diabetic and vascular ulcers; amputations", ALL("amputation"), base="amputation"),
    Page("6i-i-diabetes", "6(i)(i)", "Diabetes mellitus and diabetes insipidus", "6", "6(i) Metabolic syndrome",
         [S("diabetes", "s1"), S("diabetes", "s2", take=["-Diabetic foot", "-Foot risk"]),
          S("diabetes", "s3"), S("diabetes", "s4", take=["-Why the diabetic foot", "-Stages of wound", "-Factors affecting"],
                                 append='<p>Diabetic foot ulcers, wound healing and pressure sores are in <a href="6h-ulcers.html">6(h)</a>.</p>'),
          S("diabetes", "s5"), S("diabetes", "s6"), S("diabetes", "s7"), S("diabetes", "s8"), S("diabetes", "s9"),
          S("diabetes", "s10"), S("diabetes", "s11"),
          S("diabetes", "s12", take=["-Diabetic foot care", "-Electrotherapy for wound", "-Pressure sores"]),
          S("diabetes", "s13"), S("diabetes", "s14"), S("diabetes", "s15"),
          X(("diabetes", "s16", dict(pq=[], other=["pre", "Keywords", "Viva"], qs=[0, 2])),
            lead='<h3>Past questions (MUHS, 2016–2026)</h3><ul class="pq">'
                 '<li><span class="src">7-mark questions</span>Physiotherapy for glycaemic control in diabetes (S16). Role of physiotherapy in diabetes (W18).</li>'
                 '<li><span class="src">Inside long cases</span>Diabetes with CABG (W18, S21), PAD (W22), amputation (S18, S19, W19, S23, S25), varicose veins (S17), angina with EF 25% (S20), MI (S26).</li></ul>'
                 '<p>Diabetic foot, wound-healing and pressure-sore questions are in <a href="6h-ulcers.html">6(h)</a>.</p>')],
         base="diabetes",
         meta=dict(syllabus="Ch 6(i)(i) Diabetes (mellitus and insipidus), within metabolic syndrome",
                   priority='<span class="tier">Tier 2.</span> Exercise for diabetes was asked as 7 marks (S16, W18), and diabetes is inside 10 long cases (2016–2026).',
                   asked=chips(m7=["S16", "W18"], other=["Inside 10 long cases"]),
                   split="7-mark physiotherapy for glycaemic control; part of cardiac, vascular and amputation cases",
                   lede="Diabetes was asked as physiotherapy for glycaemic control (S16) and the role of physiotherapy in diabetes (W18), and it sits inside ten long cases (CABG, PAD, amputation, varicose veins, MI). Learn why exercise lowers blood sugar, the exercise prescription, and the precautions. The diabetic foot is in 6(h).")),
    Page("6i-ii-obesity", "6(i)(ii)", "Obesity and metabolic syndrome", "6", "6(i) Metabolic syndrome", ALL("obesity"), base="obesity"),
    Page("6j-musculoskeletal", "6(j)", "Musculoskeletal dysfunction: flail chest, scoliosis and kyphosis", "6", None,
         [S("chest-wall", "s1", code="i"), S("chest-wall", "s2", code="ii"), S("chest-wall", "s3", code="iii"), S("chest-wall", "s4")],
         base="chest-wall"),

    # ---------- Chapters 7 and 8
    Page("7-cardiac-rehab", "7", "Cardiac rehabilitation", "7", None,
         ALL("cardiac-rehab", subs={"s5": (('<a href="../ch6/valvular-acquired.html#s12">valve page</a>',
                                             '<a href="6a-iii-valvular.html#rehab">valve page</a>'),)},
             titles={"s1": "Definition and aims (7a)", "s2": "Indications: who should be referred (7b)",
                                      "s3": "Contraindications to exercise in cardiac rehab, ACSM (7b)", "s5": "Phases I–IV (7c)",
                                      "s8": "Outcome measures (7d)"}),
         base="cardiac-rehab"),
    Page("8-pulmonary-rehab", "8", "Pulmonary rehabilitation", "8", None,
         ALL("pulmonary-rehab", titles={"s1": "Definition and aims (8a)", "s2": "Indications: who should be referred (8b)",
                                        "s3": "Contraindications (8c)", "s5": "Components of management (8d)", "s6": "Outcome measures (8e)"}),
         base="pulmonary-rehab"),

    # ---------- Chapter 9
    Page("9a-9b-evaluation-monitoring", "9(a)–(b)", "ICU basic evaluation and principles of monitoring", "9", None,
         [G("9(a)", "Basic evaluation", [S("icu-physiotherapy", "s1"), S("icu-physiotherapy", "s3")]),
          G("9(b)", "Principles of ICU monitoring", [S("icu-physiotherapy", "s2"), S("icu-physiotherapy", "s4")]),
          X(("icu-physiotherapy", "s8", dict(pq=[], other=False, qs=[0], dup=True)),
            lead='<ul class="pq"><li><span class="src">W24 Q2(f), 7 marks</span>Equipment used in the ICU.</li></ul>'
                 '<p>The ventilated long cases and the other ICU questions are in the exam corner of <a href="9e-icu-conditions.html">9(e)</a>.</p>')],
         base="icu-physiotherapy",
         meta=dict(syllabus="Ch 9(a) Basic evaluation; 9(b) Principles of ICU monitoring",
                   priority='<span class="tier">High yield.</span> ICU questions are in every paper since 2023; equipment was asked as 7 marks in W24.',
                   asked=chips(m7=["W24 (equipment)"]),
                   split="7-mark ICU equipment; the first part of every ventilated long case",
                   lede="Every ventilated long case starts here: read the chart, the monitors and the settings, check safety, then treat. Equipment used in the ICU was asked as 7 marks (W24). Learn a fixed order for the ICU assessment and the safety criteria for mobilising a ventilated patient.")),
    Page("9c-ventilator-modes", "9(c)", "Mechanical ventilator modes", "9", None, ALL("mechanical-ventilation"), base="mechanical-ventilation",
         meta=dict(syllabus="Ch 9(c) Mechanical ventilator modes; 9(b) principles of ICU monitoring (reading the settings)")),
    Page("9d-suctioning-humidification", "9(d)", "Suctioning and humidification", "9", None,
         ALL("suctioning", skip=("s7",)) +
         [S("aerosol-humidification", "s2", take=["Why intubated"], dup=True, title="Humidification for intubated and ventilated patients (W17)",
            prepend='<p>The full notes on humidification and nebulisation are in <a href="../cards/aerosol-humidification.html">4(e)</a>.</p>'),
          S("suctioning", "s7")],
         base="suctioning",
         meta=dict(syllabus="Ch 9(d) Suctioning and humidification; practical: suctioning")),
    Page("9e-icu-conditions", "9(e)", "Therapeutic intervention in ICU conditions", "9", None,
         [G("•", "Physiotherapy for the ventilated patient", [S("icu-physiotherapy", "s5"), S("icu-physiotherapy", "s7"),
                                                              S("icu-physiotherapy", "s6", take=["Other ventilated"])]),
          G("i", "Tetanus and head injury", [S("icu-neurological", "s2"), S("icu-neurological", "s1")]),
          S("icu-medical", "s1", code="ii"),
          S("icu-medical", "s3", code="iii"),
          S("icu-neurological", "s4", code="iv"),
          S("icu-medical", "s6", code="v"),
          S("icu-medical", "s4", code="vi"),
          S("icu-medical", "s5", code="vii"),
          S("icu-physiotherapy", "s6", code="viii", title="ARDS", take=["ARDS on SIMV"], dup=True),
          S("icu-medical", "s2", code="ix"),
          S("icu-physiotherapy", "s6", code="x", title="Guillain–Barré syndrome", take=["GBS on SIMV"], dup=True,
            prepend='<p>GBS is the commonest neuromuscular disease seen in the ICU. Myasthenic crisis, motor neurone disease and muscular dystrophy are in <a href="../cards/icu-neurological.html#s4">(iv)</a>.</p>'),
          G("xi", "Spinal cord injury and other acute respiratory disorders", [S("icu-neurological", "s3"), S("icu-medical", "s7")]),
          X(("icu-physiotherapy", "s8", dict(sub=(("(section 6)", "(worked on this page)"),))), ("icu-neurological", "s5"), ("icu-medical", "s8"))],
         base="icu-physiotherapy",
         meta=dict(syllabus="Ch 9(e) Therapeutic intervention in (i) tetanus, head injury, (ii) pulmonary oedema, (iii) multiple organ failure, (iv) neuromuscular disease, (v) smoke inhalation, (vi) poisoning, (vii) aspiration, near drowning, (viii) ARDS, (ix) shock, (x) Guillain–Barré syndrome, (xi) spinal cord injury and other acute respiratory disorders",
                   priority='<span class="tier">High yield.</span> In 9 of 20 papers (2016–2026), including 4 ventilated long cases (GBS, ARDS, pneumonia, COPD).',
                   lede="Four long answers since 2020 put the patient on a ventilator: COPD with pneumonia (S20), GBS (S23), ARDS (S24) and pneumonia (W24). The other 9(e) conditions have not been asked on their own, but a head injury or spinal cord injury case could come next. Each condition gives what it is, the medical point that matters for physiotherapy, treatment by problem and precautions.")),

    # ---------- Chapters 10 and 11
    Page("10-functional-scales", "10", "Functional scales", "10", None,
         ALL("scales", titles={"s5": "Quality-of-life questionnaires: generic and disease-specific (10a, 10b; 3 marks in W24)"}),
         base="scales",
         meta=dict(syllabus="Ch 10 Introduction to functional scales: (a) generic and disease-specific; (b) patient's perception of disability and functioning, correlated with the therapist's evaluation")),
    Page("11-bls", "11", "Basic life support (CPCR)", "11", None, ALL("bls"), base="bls"),

    # ---------- Practical list and exam skills
    Page("practical-skills", "Practical", "Practical skills: the syllabus list, handling skills and equipment", "P", None,
         [F("practical-list")] + ALL("handling-skills", skip=("s7",)),
         base="handling-skills",
         meta=dict(syllabus="Practical list 1–10 (positioning and breathing control; airway clearance and devices; handling techniques; PNF; equipment; exercise prescription; adherence; ICU equipment; physical agents; basic life support)",
                   lede="The syllabus lists ten practical skills alongside the theory chapters. Most are taught in the chapters above; this page maps each one to its notes and adds the handling skills and equipment that are not written about elsewhere but are easy to be asked to demonstrate.")),
    Page("exam-theory", "Exam", "Answer writing for the theory paper", "E", None,
         [S("answer-writing", "s1"), S("answer-writing", "s2"),
          S("answer-writing", "s3", sub=(("(section 4)", '(<a href="../cards/answer-writing.html#s4">Chapter 5</a>)'),
                                         ("(section 5)", '(<a href="../cards/answer-writing.html#s5">Chapter 5</a>)'))),
          S("answer-writing", "s7")],
         base="answer-writing",
         meta=dict(syllabus="Theory paper: 80 marks in 3 hours (MUHS scheme, as set in the 2016–2026 papers)",
                   lede="Every one of the 20 papers (2016–2026) had the same shape, and almost every long answer asks for ICF, a functional diagnosis or impairments, goals and management. Marks follow structure as much as knowledge. This page turns the notes into answers that score; ICF and goals themselves are in Chapter 5.")),
    Page("exam-practical", "Exam", "The practical exam: long case, short case, spots and journal", "E", None, ALL("practical-exam"), base="practical-exam"),
]

# Topic sections deliberately left out, with where their content lives in this version.
DROPPED = {
    ("positioning", "s6"): ("4d-positioning-dyspnoea", "s4"),      # same positions, in full on the dyspnoea card
    ("paediatric", "s7"): ("6d-paediatric", "item-v"),               # a pointer, replaced by sections v and vi
    ("venous", "s1"): ("6a-vi-vii-venous", "item-vi"),              # definitions, split between items vi and vii
}


# ---------------------------------------------------------------- assembling

A_HREF = re.compile(r'(<a\b[^>]*?\bhref=")([^"]*)(")')
ID_RE = re.compile(r'\bid="([^"]+)"')
PAGE_SLUGS = {p.slug for p in PAGES}


def canon_links(h, folder, here_slug):
    """Rewrite topic-site links to @@slug#id@@ tokens, resolved after every page is assembled."""
    def rep(m):
        url = m.group(2)
        if re.match(r"(https?:|mailto:)", url) or url.startswith("@@"):
            return m.group(0)
        path, _, frag = url.partition("#")
        if path == "":
            if here_slug is None:            # in-page link in a fragment: already a new id
                return m.group(0)
            return f"{m.group(1)}@@{here_slug}#{frag}@@{m.group(3)}"
        name = path.rsplit("/", 1)[-1]
        if name == "index.html":
            return f"{m.group(1)}index.html{m.group(3)}"
        stem = name[:-5] if name.endswith(".html") else name
        if stem in PAGE_SLUGS:              # already a link to this version
            return m.group(0)
        if stem not in FOLDER:
            sys.exit(f"unknown link target {url}")
        return f"{m.group(1)}@@{stem}#{frag}@@{m.group(3)}"
    return A_HREF.sub(rep, h)


def h2(num, title, coded):
    cls = "n n--code" if coded else "n"
    return f'<h2><span class="{cls}">{num}</span>{title}</h2>'


def code_id(code):
    key = re.sub(r"[^0-9a-z]+", "-", code.lower().replace("(", "").replace(")", "")).strip("-")
    return "item-" + (key or "intro")


class Assembler:
    def __init__(self):
        self.loc = {}          # (topic slug, old id) -> (page slug, new id)
        self.primary = {}      # topic slug -> page slug holding its first section
        self.pages = {}        # page slug -> dict(body, toc, sources, ids)
        self.warnings = []

    # -- ids
    def claim(self, page, h, owner, used):
        """Make every id in h unique on the page; record where topic ids landed."""
        ren = {}
        for i in ID_RE.findall(h):
            new, k = i, 2
            while new in used:
                new, k = f"{i}-{k}", k + 1
            used.add(new)
            if new != i:
                ren[i] = new
            if owner:
                self.own(owner, i, page, new)
        for old, new in ren.items():
            h = h.replace(f'id="{old}"', f'id="{new}"', 1)
            h = h.replace(f"url(#{old})", f"url(#{new})")
            h = re.sub(rf'(aria-(?:labelledby|describedby)="(?:[^"]*\s)?){re.escape(old)}(?=[\s"])', rf"\g<1>{new}", h)
        return h

    def own(self, src, old_id, page, new_id):
        key = (src, old_id)
        if key in self.loc:
            self.warnings.append(f"{src}#{old_id} placed twice ({self.loc[key][0]} and {page})")
            return
        self.loc[key] = (page, new_id)
        if old_id == "s1" or src not in self.primary:
            self.primary.setdefault(src, page)
            if old_id == "s1":
                self.primary[src] = page

    # -- blocks
    def section(self, page, blk, num, coded, used, renum):
        sec = parse_sec(topic(blk.src)[1][blk.sid])
        kids = select(sec["kids"], blk.take, f"{page.slug}: {blk.src}#{blk.sid}")
        title = blk.title or sec["title"]
        if blk.lift and kids and kids[0].startswith("<h3"):
            title = blk.title or re.match(r"<h3[^>]*>(.*?)</h3>", kids[0], re.S).group(1).strip()
            kids = kids[1:]
        new_id = blk.anchor or (code_id(blk.code) if coded else f"s{num}")
        if blk.sub:
            joined = "\n    ".join(kids)
            for old, new in blk.sub:
                if old not in joined:
                    sys.exit(f"{page.slug}: '{old}' not found in {blk.src}#{blk.sid}")
                joined = joined.replace(old, new)
            kids = [joined]
        folder = FOLDER[blk.src]
        pre = canon_links(blk.prepend, folder, blk.src) if blk.prepend else ""
        post = canon_links(blk.append, folder, blk.src) if blk.append else ""
        body = "\n    ".join([pre] + [canon_links(k, folder, blk.src) for k in kids] + [post])
        toc = blk.toc or (sec["toc"] if not blk.title else None)
        toc_attr = f' data-toc="{html.escape(toc)}"' if toc else ""
        used.add(new_id)
        if not blk.dup:
            self.own(blk.src, blk.sid, page.slug, new_id)
        if not coded and blk.take is None:
            renum.setdefault(blk.src, {})[sec["num"]] = str(num)
        body = self.claim(page.slug, body, None if blk.dup else blk.src, used)
        label = toc or plain(title)
        return (f'  <section class="sec" id="{new_id}"{toc_attr}>\n    {h2(blk.code if coded else num, title, coded)}\n    {body}\n  </section>',
                new_id, blk.code if coded else str(num), label, {blk.src})

    def group(self, page, blk, num, used):
        new_id = code_id(blk.code)
        used.add(new_id)
        parts_html, srcs = [], set()
        if blk.prepend:
            parts_html.append(canon_links(blk.prepend, FOLDER[blk.parts[0].src], blk.parts[0].src))
        for k, part in enumerate(blk.parts, start=1):
            sec = parse_sec(topic(part.src)[1][part.sid])
            kids = select(sec["kids"], part.take, f"{page.slug}: {part.src}#{part.sid}")
            if part.lift and kids and kids[0].startswith("<h3"):
                kids = kids[1:]
            folder = FOLDER[part.src]
            content = "\n    ".join(canon_links(x, folder, part.src) for x in kids)
            content = self.claim(page.slug, content, None if part.dup else part.src, used)
            if part.title is None and part.take is not None:
                anchor = new_id
                parts_html.append(content)
            else:
                anchor = f"{new_id}-{k}"
                used.add(anchor)
                title = part.title or sec["title"]
                parts_html.append(f'<h3 id="{anchor}">{title}</h3>\n    {demote(content)}')
            if not part.dup:
                self.own(part.src, part.sid, page.slug, anchor)
            srcs.add(part.src)
        body = "\n    ".join(parts_html)
        toc_attr = f' data-toc="{html.escape(blk.toc)}"' if blk.toc else ""
        return (f'  <section class="sec" id="{new_id}"{toc_attr}>\n    {h2(blk.code, blk.title, True)}\n    {body}\n  </section>',
                new_id, blk.code, blk.toc or plain(blk.title), srcs)

    def fragment(self, page, blk, counter, used):
        path = FRAG_DIR / f"{blk.name}.html"
        text = path.read_text(encoding="utf-8")
        m = re.match(r"\s*<!--(.*?)-->\s*(.*)\Z", text, re.S)
        head = dict(line.split(":", 1) for line in m.group(1).strip().splitlines() if ":" in line)
        head = {k.strip(): v.strip() for k, v in head.items()}
        folder = head.get("base", "ch6")
        srcs = {s.strip() for s in head.get("sources", "").split(",") if s.strip()}
        out = []
        for sm in re.finditer(r'<section class="sec[^"]*" id="([^"]+)"[^>]*>.*?</section>', m.group(2), re.S):
            sec = parse_sec(sm.group(0))
            coded = sec["num"] != "#"
            if coded:
                num = sec["num"]
            else:
                counter[0] += 1
                num = str(counter[0])
            new_id = sec["sid"]
            if new_id in used:
                sys.exit(f"{page.slug}: fragment id {new_id} already used")
            used.add(new_id)
            body = "\n    ".join(canon_links(k, folder, None) for k in sec["kids"])
            body = self.claim(page.slug, body, None, used)
            toc_attr = f' data-toc="{html.escape(sec["toc"])}"' if sec["toc"] else ""
            out.append((f'  <section class="sec" id="{new_id}"{toc_attr}>\n    {h2(num, sec["title"], coded)}\n    {body}\n  </section>',
                        new_id, num, sec["toc"] or plain(sec["title"]), set()))
        for pair in head.get("alias", "").split(","):
            if "=" in pair:
                old, new = (x.strip() for x in pair.split("="))
                src, _, oid = old.partition("#")
                self.own(src, oid, page.slug, new)
        if out:
            out[0] = out[0][:4] + (srcs,)
        return out

    def exam(self, page, blk, num, used):
        pq, qs, other, leads, srcs = [], [], [], [], set()
        for src, sid, opts in blk.parts:
            sec = parse_sec(topic(src)[1][sid])
            folder = FOLDER[src]
            p_items, q_items, o_kids = [], [], []
            for k in sec["kids"]:
                if k.startswith('<ul class="pq"'):
                    p_items += [c for c in children(inner(k)) if c.startswith("<li")]
                elif k.startswith('<div class="selftest"'):
                    for c in children(inner(k)):
                        if c.startswith("<details"):
                            q_items.append(c)
                        elif c.startswith("<p") and not leads:
                            leads.append(c)
                else:
                    o_kids.append(k)
            gs = []
            for key, ks in groups(o_kids):
                if key != "pre" and key.lower().startswith("past questions"):
                    gs.append(("pre", ks[1:]))     # keep what follows the list, such as technique-card links
                else:
                    gs.append((key, ks))
            if opts.get("pq") is not None:
                p_items = [p_items[i] for i in opts["pq"]]
            if opts.get("qs") is not None:
                q_items = [q_items[i] for i in opts["qs"]]
            keep = opts.get("other", True)
            if keep is False:
                gs = []
            elif keep is not True:
                gs = [g for g in gs if any((sel == "pre" and g[0] == "pre") or (g[0] != "pre" and g[0].lower().startswith(sel.lower()))
                                           for sel in keep)]
            for old, new in opts.get("sub", ()):
                if not any(old in x for x in p_items + q_items + [k for _, ks in gs for k in ks]):
                    sys.exit(f"{page.slug}: '{old}' not found in {src}#{sid}")
                p_items = [x.replace(old, new) for x in p_items]
                q_items = [x.replace(old, new) for x in q_items]
                gs = [(key, [k.replace(old, new) for k in ks]) for key, ks in gs]
            pq += [canon_links(x, folder, src) for x in p_items]
            qs += [canon_links(x, folder, src) for x in q_items]
            other += [canon_links(x, folder, src) for _, ks in gs for x in ks]
            if not opts.get("dup"):
                self.own(src, sid, page.slug, f"s{num}")
            srcs.add(src)
        parts = [canon_links(blk.lead, "cards", None)] if blk.lead else []
        if pq:
            parts.append("<h3>Past questions (MUHS, 2016–2026)</h3>\n    <ul class=\"pq\">\n      " + "\n      ".join(pq) + "\n    </ul>")
        parts += other
        if qs:
            parts.append('<div class="selftest">\n      <h3>Test yourself</h3>\n      ' + "\n      ".join(leads[:1] + qs) + "\n    </div>")
        new_id = f"s{num}"
        used.add(new_id)
        body = self.claim(page.slug, "\n    ".join(parts), None, used)
        return (f'  <section class="sec" id="{new_id}">\n    {h2(num, "Exam corner", False)}\n    {body}\n  </section>',
                new_id, str(num), "Exam corner", srcs)

    def assemble(self, page):
        pieces, used, renum, counter = [], {"sources"}, {}, [0]
        for blk in page.blocks:
            if isinstance(blk, F):
                pieces += self.fragment(page, blk, counter, used)
                continue
            if isinstance(blk, S) and blk.code is None:
                counter[0] += 1
                pieces.append(self.section(page, blk, counter[0], False, used, renum))
            elif isinstance(blk, S):
                pieces.append(self.section(page, blk, None, True, used, renum))
            elif isinstance(blk, G):
                pieces.append(self.group(page, blk, None, used))
            elif isinstance(blk, X):
                counter[0] += 1
                pieces.append(self.exam(page, blk, counter[0], used))
        # rewrite "section N" in text taken from renumbered topic sections
        srcs = set(page.extra_sources)
        for p in pieces:
            srcs |= p[4]
        for i, p in enumerate(pieces):
            if len(p[4]) != 1:
                continue
            (src,) = p[4]
            nums = renum.get(src, {})
            if all(k == v for k, v in nums.items()):
                continue

            def fix(m, nums=nums, src=src, pslug=page.slug):
                n = m.group(2)
                if n in nums:
                    return f"{m.group(1)}{nums[n]}"
                self.warnings.append(f"{pslug}: text from {src} mentions section {n}, which is not on this page")
                return m.group(0)
            pieces[i] = (re.sub(r"\b(sections? )(\d+)\b", fix, p[0]),) + p[1:]
        self.pages[page.slug] = dict(pieces=pieces, srcs=srcs, used=used)

    # -- links
    def resolve(self, page_slug, h):
        def rep(m):
            src, _, frag = m.group(1).partition("#")
            if frag and (src, frag) in self.loc:
                tgt, new = self.loc[(src, frag)]
            elif frag and (src, frag) in DROPPED:
                tgt, new = DROPPED[(src, frag)]
            else:
                tgt, new = self.primary.get(src), ""
                if tgt is None:
                    self.warnings.append(f"{page_slug}: link to {src}#{frag}, a topic placed on no page")
                    return "index.html"
                if frag:
                    self.warnings.append(f"{page_slug}: link to {src}#{frag} falls back to {tgt}.html")
            if tgt == page_slug:
                return f"#{new}" if new else "#"
            return f"{tgt}.html" + (f"#{new}" if new else "")
        return re.sub(r"@@([^@]+)@@", rep, h)


# ---------------------------------------------------------------- output

def sources_html(slugs):
    seen, items = set(), []
    for s in slugs:
        sec = topic(s)[1].get("sources", "")
        m = re.search(r"<ol>(.*?)</ol>", sec, re.S)
        for li in re.findall(r"<li>.*?</li>", m.group(1), re.S) if m else []:
            key = plain(li).lower()
            if key not in seen:
                seen.add(key)
                items.append(li)
    return items


def page_meta(page):
    base = topic(page.base)[0] if page.base else {}
    meta = {k: base.get(k, "") for k in ("description", "lede", "syllabus", "priority", "asked", "split", "checked", "date", "review")}
    meta["title"] = f"{page.code} {page.h1}" if page.chapter not in ("P", "E") else page.h1
    meta.update(page.meta_over)
    for k in ("date", "review"):
        meta[k] = meta[k] or "19 October 2026"
    return meta


def retext(body):
    """The topic site calls its technique pages "cards"; in this version every topic is a syllabus page."""
    parts = re.split(r"(<[^>]+>)", body)
    for i in range(0, len(parts), 2):
        t = parts[i].replace("Technique cards for this topic", "Related pages")
        t = re.sub(r"(?<!device )\bcard\b", "page", t)
        parts[i] = re.sub(r"\bcards\b", "pages", t)
    return "".join(parts)


def page_body(page, asm):
    """The finished notes of one page (sections, then sources), with links resolved; also used by print_syllabus.py."""
    data = asm.pages[page.slug]
    meta = page_meta(page)
    srcs = [s for s in [page.base] + sorted(data["srcs"] - {page.base}) if s]
    body = "\n\n".join(p[0] for p in data["pieces"])
    items = sources_html(srcs)
    body += ('\n\n  <section class="sec sources" id="sources">\n    <h2><span class="n">&nbsp;</span>Sources</h2>\n    <ol>\n      '
             + "\n      ".join(items) + "\n    </ol>\n    <div class=\"pagefoot\">\n"
             "      <p>Educational notes for exam preparation. Not medical advice.</p>\n"
             f"      <p>Syllabus-order version. Content checked {meta['date']}. Next review {meta['review']}.</p>\n    </div>\n  </section>")
    body = canon_links(body, "cards", None)
    body = asm.resolve(page.slug, body)
    return meta, build.add_abbr(retext(body))


def write_page(page, prev_p, next_p, asm):
    data = asm.pages[page.slug]
    meta, body = page_body(page, asm)
    toc = "\n".join(f'    <li><a href="#{sid}"><span class="n">{html.escape(num)}</span>{html.escape(html.unescape(label))}</a></li>'
                    for _, sid, num, label, _ in data["pieces"])
    nav = []
    if prev_p:
        nav.append(f'<a class="pagenav__prev" href="{prev_p.slug}.html"><span>Previous in the syllabus</span>{prev_p.code} {html.escape(prev_p.h1)}</a>')
    if next_p:
        nav.append(f'<a class="pagenav__next" href="{next_p.slug}.html"><span>Next in the syllabus</span>{next_p.code} {html.escape(next_p.h1)}</a>')
    pagenav = f'  <nav class="pagenav" aria-label="Other pages">\n    {"".join(nav)}\n  </nav>\n' if nav else ""
    crumbs = ['<a href="../index.html">Home</a>', f'<a href="index.html">{SITE_NAME}</a>', crumb_for(page.chapter)]
    if page.crumb:
        crumbs.append(page.crumb)
    up = "../"
    desc = retext(plain(meta["description"]).replace("Technique card for", "Notes for"))
    out = build.HEAD.format(title=html.escape(plain(meta["title"])), description=html.escape(desc), up=up)
    out = out.replace(f'<link rel="stylesheet" href="{up}assets/notes.css">',
                      f'<link rel="stylesheet" href="{up}assets/notes.css">\n<link rel="stylesheet" href="{up}assets/syllabus.css">')
    out += f"""<a class="skip" href="#content">Skip to notes</a>

<header class="topbar">
  <button class="iconbtn js-toc-btn" type="button" aria-controls="toc" aria-expanded="false">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
    Contents
  </button>
  <div class="topbar__title"><a href="index.html">{SITE_NAME}</a></div>
  {build.THEME_BTN}
  <svg class="trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
</header>

<div class="layout">
<nav class="toc" id="toc" aria-label="Contents of this page">
  <h2>On this page</h2>
  <ol>
{toc}
  </ol>
  <div class="toc__extra">
    <a href="index.html">All syllabus chapters</a>
  </div>
</nav>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs">{" › ".join(crumbs)}</p>
      <h1><span class="h1code">{page.code}</span>{html.escape(page.h1)}</h1>
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
    (OUT / f"{page.slug}.html").write_text(out, encoding="utf-8")
    return out


def item_note(target):
    slug = target.split("#")[0]
    page = next(p for p in PAGES if p.slug == slug)
    return plain(page_meta(page)["priority"])


def write_index():
    def link(target, label):
        return f'<a href="{target.replace("#", ".html#", 1) if "#" in target else target + ".html"}">{html.escape(label)}</a>'

    def notes(items):
        """The page's priority line, or "Same page as (x)" when the previous item opens the same page."""
        out, prev = [], (None, None)
        for code, target in items:
            page = target.split("#")[0] if isinstance(target, str) else None
            out.append(f"Same page as ({prev[0]})" if page and page == prev[1] else (item_note(target) if page else ""))
            if page != prev[1]:
                prev = (code, page)
        return out

    def item_li(code, wording, target, subs, note):
        badge = f'<span class="syl-code">{code}</span>' if code else '<span class="syl-code syl-code--none"></span>'
        if subs:
            head = link(target, wording) if target else f'<span class="syl-ttl">{html.escape(wording)}</span>'
            rows = "\n".join(
                f'          <li><span class="syl-code">{c}</span><div>{link(t, w)}'
                f'<span class="meta">{html.escape(n)}</span></div></li>'
                for (c, w, t), n in zip(subs, notes([(c, t) for c, _, t in subs])))
            return f'      <li>{badge}<div>{head}\n        <ol class="syl-sub">\n{rows}\n        </ol></div></li>'
        if isinstance(target, list):
            rows = "\n".join(
                f'          <li><span class="syl-code syl-code--none"></span><div>{link(t, next(p.h1 for p in PAGES if p.slug == t))}'
                f'<span class="meta">{html.escape(item_note(t))}</span></div></li>' for t in target)
            return (f'      <li>{badge}<div><span class="syl-ttl">{html.escape(wording)}</span>\n        <ol class="syl-sub">\n{rows}\n        </ol></div></li>')
        return f'      <li>{badge}<div>{link(target, wording)}<span class="meta">{html.escape(note)}</span></div></li>'

    sections, jump = [], []
    for key, title, hours, items in CHAPTERS + EXTRA_PARTS:
        anchor = f"ch{key.lower()}"
        jump.append(f'<a href="#{anchor}">{key}</a>')
        lis = "\n".join(item_li(*it, n) for it, n in zip(items, notes([(it[0], it[2]) for it in items])))
        label = f"Chapter {key}: " if key.isdigit() else ""
        sections.append(f"""    <section class="sec syl-ch" id="{anchor}">
      <h2><span class="n{' n--code' if not key.isdigit() else ''}">{key}</span>{html.escape(title)}</h2>
      <p class="meta-line">{label}{html.escape(hours)}</p>
      <ol class="syl-items">
{lis}
      </ol>
    </section>""")
    out = build.HEAD.format(title="CVR Physiotherapy by syllabus",
                            description="MUHS final-year BPTh Cardio-Vascular and Respiratory Physiotherapy notes in the order of the 2012 syllabus, Chapters 1 to 11.",
                            up="../")
    out = out.replace('<link rel="stylesheet" href="../assets/notes.css">',
                      '<link rel="stylesheet" href="../assets/notes.css">\n<link rel="stylesheet" href="../assets/syllabus.css">')
    out += f"""<a class="skip" href="#content">Skip to the chapters</a>
<header class="topbar">
  <div class="topbar__title">{SITE_NAME}</div>
  {build.THEME_BTN}
</header>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs"><a href="../index.html">Home</a> › {SITE_NAME}</p>
      <h1>Cardio-Vascular and Respiratory Physiotherapy, in syllabus order</h1>
      <p class="lede">Chapters 1 to 11 of the MUHS syllabus, then the practical list and exam skills, in the order your college teaches them. These are the same notes as the <a href="../cvr/index.html">topic-wise version</a>, which puts Chapter 6 in the order the topics score in the papers.</p>
      <nav class="syl-jump" aria-label="Chapters">{"".join(jump)}</nav>
    </div>
  </div>

  <div class="wrap">
    <section class="sec" id="how">
      <h2><span class="n">?</span>How to use these notes</h2>
      <ol>
        <li><strong>Follow your classes.</strong> Open the chapter your college is teaching. Each syllabus item below links to its notes.</li>
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
        <p>Under each item, the grey line says how often it was asked from Summer 2016 to Summer 2026. Since 2023 an ICU question has appeared in every paper, so give Chapter 9 the same time as the Tier 1 conditions in Chapter 6.</p>
      </div>
    </section>

{chr(10).join(sections)}

    <div class="pagefoot">
      <p>Educational notes for exam preparation. Not medical advice. Written in original words from current textbooks and dated guidelines; sources are listed on each page.</p>
    </div>
  </div>
</main>
<script src="../assets/notes.js"></script>
</body>
</html>
"""
    (OUT / "index.html").write_text(out, encoding="utf-8")


# ---------------------------------------------------------------- checks

def check(asm, written):
    problems = list(asm.warnings)
    ids = {}
    for slug, text in written.items():
        found = ID_RE.findall(text)
        dupes = {i for i in found if found.count(i) > 1}
        if dupes:
            problems.append(f"{slug}: duplicate ids {sorted(dupes)}")
        ids[slug] = set(found)
    for slug, text in written.items():
        for m in A_HREF.finditer(text):
            url = m.group(2)
            if re.match(r"(https?:|mailto:)", url) or url.startswith("../"):
                continue
            path, _, frag = url.partition("#")
            target = slug if path == "" else path[:-5]
            if target not in written:
                problems.append(f"{slug}: link to missing page {url}")
            elif frag and frag not in ids[target]:
                problems.append(f"{slug}: link to missing id {url}")
    for chapter in CHAPTERS + EXTRA_PARTS:
        for code, wording, target, subs in chapter[3]:
            for t in ([target] if isinstance(target, str) else target or []) + [s[2] for s in subs or []]:
                p, _, frag = t.partition("#")
                if p not in written or (frag and frag not in ids[p]):
                    problems.append(f"index: syllabus item {chapter[0]}{code} points to missing {t}")
    placed = set(asm.loc) | set(DROPPED)
    for src in sorted(FOLDER):
        for sid in topic(src)[2]:
            if sid != "sources" and (src, sid) not in placed:
                problems.append(f"not used anywhere: {src}#{sid}")
    return problems


def main():
    OUT.mkdir(exist_ok=True)
    asm = Assembler()
    for page in PAGES:
        asm.assemble(page)
    written = {}
    for i, page in enumerate(PAGES):
        written[page.slug] = write_page(page, PAGES[i - 1] if i else None, PAGES[i + 1] if i + 1 < len(PAGES) else None, asm)
    write_index()
    written["index"] = (OUT / "index.html").read_text(encoding="utf-8")
    keep = {f"{p.slug}.html" for p in PAGES} | {"index.html"}
    for stale in OUT.glob("*.html"):
        if stale.name not in keep:
            stale.unlink()
    problems = check(asm, written)
    print(f"built {len(PAGES)} syllabus pages and the contents page in {OUT.relative_to(ROOT)}/")
    for p in problems:
        print("  " + p)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
