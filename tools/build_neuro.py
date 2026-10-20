#!/usr/bin/env python3
"""Build the Neurophysiotherapy notes into neuro/.

The pages follow the MUHS 2012 syllabus from the start: Chapters 1 to 4, the
assessment topics that apply to every condition, Chapter 5A (adult conditions,
then the treatment programme), Chapter 5B (paediatric), and exam skills.

Each page's source is src/neuro/<slug>.html: a metadata comment followed by
<section class="sec"> blocks, in the same format as the CVR pages (STYLE.md).
Pages without a source yet appear on the contents page as "Coming".

Run from anywhere:  python3 tools/build_neuro.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  shared frame, abbreviations, metadata parser

ROOT = build.ROOT
SRC = build.SRC / "neuro"
OUT = ROOT / "neuro"
SITE_NAME = "Neuro Physiotherapy"

# Parts of the syllabus, in order: key, title, hours or note.
PARTS = [
    ("1", "Application of the ICF model", "2 hours theory"),
    ("2", "Theoretical basis of motor control and learning", "2 hours theory"),
    ("3", "Plasticity and recovery, strength training and skill acquisition", "5 hours theory"),
    ("4", "Quality of life scales and independence measures", "2 hours theory"),
    ("G", "Assessment for every condition", "Evaluation, investigations, movement dysfunction and outcome tools"),
    ("5A", "Physiotherapy management: adult conditions", "37 hours theory, 95 practical"),
    ("TP", "Physiotherapy management: the adult treatment programme", "Treatment programme items 1 to 9"),
    ("5B", "Physiotherapy management: paediatric conditions", "17 hours theory, 40 practical"),
    ("E", "Exam skills", "How the notes become marks"),
]

# Pages in syllabus order: slug, syllabus code, title, part, note shown on the contents page until the page is written.
PAGES = [
    ("1-icf", "1", "Application of the ICF model in neurological conditions", "1", "ICF is asked in almost every long case; domains of ICF as 7 marks (S19)."),
    ("2-motor-control", "2", "Motor control: theories behind neurological physiotherapy", "2", "Theories of motor control as 7 marks in W19, S21 and S23."),
    ("3-plasticity-learning", "3", "Neuroplasticity, recovery, motor learning and skill acquisition", "3", "Motor learning stages and feedback in 6 papers; neuroplasticity in 3."),
    ("4-scales", "4", "Quality of life, independence and other outcome measures", "4", "GCS, Modified Ashworth, ASIA and Hoehn and Yahr as 3-mark questions."),
    ("g-assessment", "G", "Neurological assessment and investigations", "G", "Tone, reflexes, sensation, coordination; EMG and nerve conduction are practical spots."),
    ("g-cognition-perception", "G", "Cognition, perception, apraxia and aphasia", "G", "Apraxia, aphasia, neglect and cortical sensations in 9 papers."),
    ("g-movement-dysfunction", "G", "Movement dysfunction in daily tasks: bed mobility to reaching", "G", "The functional tasks the syllabus lists for every condition."),
    ("5a-a-stroke", "5A(a)", "Stroke", "5A", "11 long cases and 13 seven-mark questions in 20 papers."),
    ("5a-b-brain-injury", "5A(b)", "Acquired brain injury: trauma and space-occupying lesions", "5A", "5 long cases; GCS and raised intracranial pressure as 3 marks."),
    ("5a-c-spinal-cord", "5A(c)", "Spinal cord disorders: traumatic and non-traumatic", "5A", "9 long cases; autonomic dysreflexia and bladder in almost every paper."),
    ("5a-d-nerve-injuries", "5A(d)", "Peripheral nerve injuries and the brachial plexus", "5A", "Nerve injury classification 5 times; radial, Erb's, Klumpke's, peroneal."),
    ("5a-d-neuropathies", "5A(d)", "Peripheral neuropathies and nerve root lesions", "5A", "Diabetic neuropathy 5 times; leprosy, alcoholic neuropathy, CRPS."),
    ("5a-e-vestibular", "5A(e)", "Vestibular disorders", "5A", "8 seven-mark questions: BPPV, adaptation, habituation, tests."),
    ("5a-f-facial-nerve", "5A(f)", "Facial (VII) nerve palsy and other cranial nerves", "5A", "Bell's palsy in 6 papers; trigeminal neuralgia twice."),
    ("5a-g-multiple-sclerosis", "5A(g)", "Multiple sclerosis", "5A", "6 long cases; the second-relapse executive case was asked 3 times."),
    ("5a-g-gbs", "5A(g)", "Guillain–Barré syndrome", "5A", "9 long cases, often ventilated or just out of the ICU."),
    ("5a-h-ataxia", "5A(h)", "Cerebellar disease and ataxia", "5A", "3 long cases (Friedreich's twice, cerebellar stroke) and 3 seven-mark questions."),
    ("5a-i-parkinsons", "5A(i)", "Parkinson's disease and other extrapyramidal disorders", "5A", "7 long cases and 6 seven-mark questions."),
    ("5a-j-anterior-horn-cell", "5A(j)", "Anterior horn cell diseases: MND, SMA and poliomyelitis", "5A", "ALS long cases (S16, W16); MND types and terminal care."),
    ("5a-k-myopathies", "5A(k)", "Myopathies and myasthenia gravis", "5A", "Myasthenia gravis as 7 marks (W19) and 3 marks (W24)."),
    ("5a-l-autonomic", "5A(l)", "Disorders of the autonomic nervous system", "5A", "Horner's syndrome; blood-pressure disorders; autonomic dysreflexia."),
    ("5a-m-psychosomatic", "5A(m)", "Psychosomatic pain and paralysis", "5A", "In the syllabus; not asked on its own in 2016–2026."),
    ("tp1-electrotherapy", "TP1", "Electrotherapy in neurological rehabilitation", "TP", "Pain relief and functional re-education with electrical stimulation."),
    ("tp2-approaches", "TP2", "Neurotherapeutic approaches: Brunnstrom, Rood, Bobath, MRP, PNF and CIMT", "TP", "Rood, Bobath, MRP and PNF in 8 papers."),
    ("tp2-tone", "TP2", "Managing tone: spasticity, rigidity and hypotonia", "TP", "Tone techniques in 9 papers."),
    ("tp2-balance-coordination", "TP2", "Balance and coordination training", "TP", "Balance strategies and training in 4 papers."),
    ("tp3-equipment", "TP3", "Tools and adaptive equipment for neuro-rehabilitation", "TP", "Balls, tilt boards, bolsters, wedges, benches and mats."),
    ("tp4-transfers-gait", "TP4", "Transfers, functional re-education, posture and gait training", "TP", "Gait training appears inside most stroke and Parkinson's answers."),
    ("tp5-bladder-bowel", "TP5", "Bladder and bowel training", "TP", "Types of neurogenic bladder in 9 papers."),
    ("tp6-caring", "TP6", "A philosophy of caring", "TP", "Patient- and family-centred care."),
    ("tp7-orthoses", "TP7", "Orthoses and splints", "TP", "AFO, cock-up splints and CP foot orthoses; a practical spot."),
    ("tp8-wheelchairs", "TP8", "Lifting, wheelchairs and adaptive devices", "TP", "Wheelchair prescription in DMD (S26)."),
    ("tp9-ergonomics", "TP9", "Ergonomic advice and caregiver education", "TP", "Home-care advice to parents and caregivers in several long cases."),
    ("5b-development", "5B", "Developmental neurology: milestones, reflexes and reactions", "5B", "Milestones as 7 marks in 3 papers; ATNR, parachute and other reflexes."),
    ("5b-1-cerebral-palsy", "5B(1)", "Cerebral palsy", "5B", "13 long cases in 20 papers, the most of any topic."),
    ("5b-2-down-syndrome", "5B(2)", "Down's syndrome", "5B", "3 seven-mark questions."),
    ("5b-3-spina-bifida", "5B(3)", "Neural tube defects: spina bifida and hydrocephalus", "5B", "11 short questions in 9 papers."),
    ("5b-4-brachial-plexus", "5B(4)", "Obstetric brachial plexus injury", "5B", "A 6-month-old with Erb's palsy (S19)."),
    ("5b-5-infections", "5B(5)", "Infections of the nervous system", "5B", "Kernig's and Brudzinski's signs twice."),
    ("5b-6-pprp", "5B(6)", "Post-polio residual paralysis", "5B", "PPRP in 4 papers."),
    ("5b-7-dmd", "5B(7)", "Duchenne muscular dystrophy and other myopathies", "5B", "6 long cases and 7 seven-mark questions."),
    ("5b-8-sma-hsmn", "5B(8)", "Spinal muscular atrophy and hereditary neuropathies", "5B", "In the syllabus; not asked on its own in 2016–2026."),
    ("5b-9-extrapyramidal", "5B(9)", "Paediatric extrapyramidal disorders", "5B", "Dyskinetic and athetoid CP cases (W25)."),
    ("exam-theory", "Exam", "Answer writing for the Neuro paper", "E", "The paper, ICF in long cases, and answer skeletons."),
    ("exam-practical", "Exam", "The Neuro practical exam: long case, short case, spots and journal", "E", "Spots: EMG and nerve conduction, orthoses, prostheses, scales."),
]

PART_CRUMB = {
    "1": "Chapter 1", "2": "Chapter 2", "3": "Chapter 3", "4": "Chapter 4", "G": "Assessment",
    "5A": "Chapter 5A: adult", "TP": "Chapter 5A: treatment programme", "5B": "Chapter 5B: paediatric", "E": "Exam skills",
}

# Abbreviations for neurology, added to the shared list. Ambiguous ones (AIS, AD, VC) are written out by hand.
NEURO_ABBR = {
    "CP": "Cerebral palsy", "SCI": "Spinal cord injury", "MS": "Multiple sclerosis", "PD": "Parkinson's disease",
    "TBI": "Traumatic brain injury", "GCS": "Glasgow Coma Scale", "MAS": "Modified Ashworth Scale",
    "BBS": "Berg Balance Scale", "TUG": "Timed Up and Go test", "DGI": "Dynamic Gait Index",
    "MMSE": "Mini-Mental State Examination", "MoCA": "Montreal Cognitive Assessment",
    "UMN": "Upper motor neuron", "LMN": "Lower motor neuron", "MND": "Motor neuron disease",
    "ALS": "Amyotrophic lateral sclerosis", "DMD": "Duchenne muscular dystrophy", "SMA": "Spinal muscular atrophy",
    "PPRP": "Post-polio residual paralysis", "BPPV": "Benign paroxysmal positional vertigo",
    "MCA": "Middle cerebral artery", "ACA": "Anterior cerebral artery", "PCA": "Posterior cerebral artery",
    "AFO": "Ankle–foot orthosis", "KAFO": "Knee–ankle–foot orthosis", "CIMT": "Constraint-induced movement therapy",
    "MRP": "Motor Relearning Programme", "NDT": "Neurodevelopmental treatment (Bobath)",
    "UPDRS": "Unified Parkinson's Disease Rating Scale", "EDSS": "Expanded Disability Status Scale",
    "FMA": "Fugl-Meyer Assessment", "NIHSS": "National Institutes of Health Stroke Scale", "mRS": "Modified Rankin Scale",
    "EMG": "Electromyography", "NCS": "Nerve conduction studies", "NCV": "Nerve conduction velocity",
    "CSF": "Cerebrospinal fluid", "SOL": "Space-occupying lesion", "SDH": "Subdural haematoma",
    "DAI": "Diffuse axonal injury", "GMFCS": "Gross Motor Function Classification System",
    "ATNR": "Asymmetrical tonic neck reflex", "STNR": "Symmetrical tonic neck reflex",
    "NMES": "Neuromuscular electrical stimulation", "FES": "Functional electrical stimulation",
    "IVIG": "Intravenous immunoglobulin", "TIA": "Transient ischaemic attack", "AF": "Atrial fibrillation",
    "CT": "Computed tomography", "MRI": "Magnetic resonance imaging", "10MWT": "10-metre walk test",
    "ASIA": "American Spinal Injury Association", "CMT": "Charcot–Marie–Tooth disease",
    "HSMN": "Hereditary sensory and motor neuropathy", "ASA": "American Stroke Association",
    "EEG": "Electroencephalography", "HKAFO": "Hip–knee–ankle–foot orthosis",
    "ISNCSCI": "International Standards for Neurological Classification of Spinal Cord Injury",
    "STREAM": "Stroke Rehabilitation Assessment of Movement",
    "ADIP": "Assistance to Disabled Persons for purchase of aids and appliances (scheme)",
    "ALIMCO": "Artificial Limbs Manufacturing Corporation of India",
    "CDC": "Centers for Disease Control and Prevention (USA)", "CFCS": "Communication Function Classification System",
    "CIDP": "Chronic inflammatory demyelinating polyneuropathy", "CNS": "Central nervous system",
    "COMT": "Catechol-O-methyltransferase", "CPP": "Cerebral perfusion pressure",
    "CRPS": "Complex regional pain syndrome", "CVA": "Cerebrovascular accident (stroke)",
    "DASH": "Disabilities of the Arm, Shoulder and Hand questionnaire", "EAN": "European Academy of Neurology",
    "EAU": "European Association of Urology", "EFNS": "European Federation of Neurological Societies",
    "ESR": "Erythrocyte sedimentation rate", "GMCH": "Government Medical College and Hospital",
    "HINTS": "Head impulse, nystagmus, test of skew (bedside stroke check in acute vertigo)",
    "ICMR-INDIAB": "ICMR–India Diabetes study", "IQ": "Intelligence quotient", "JE": "Japanese encephalitis",
    "LSVT": "Lee Silverman Voice Treatment", "MAO-B": "Monoamine oxidase B",
    "MDS": "International Parkinson and Movement Disorder Society",
    "MDS-UPDRS": "Movement Disorder Society Unified Parkinson's Disease Rating Scale",
    "MEP": "Maximal expiratory pressure", "MGFA": "Myasthenia Gravis Foundation of America",
    "NGO": "Non-governmental organisation", "NICU": "Neonatal intensive care unit", "OPD": "Outpatient department",
    "PDQ-39": "Parkinson's Disease Questionnaire (39 items)", "PMA": "Progressive muscular atrophy",
    "PNS": "Peripheral Nerve Society", "RTA": "Road traffic accident", "VP": "Ventriculoperitoneal (shunt)",
}

TOC_RE = re.compile(r'<section class="sec[^"]*" id="([^"]+)"(?: data-toc="([^"]*)")?>\s*<h2><span class="n[^"]*">([^<]*)</span>(.*?)</h2>', re.S)


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


def ready_pages():
    return [p for p in PAGES if (SRC / f"{p[0]}.html").exists()]


def unlink_unwritten(text, ready):
    """Links to Neuro pages that are not written yet become plain text until the page exists."""
    slugs = {p[0] for p in PAGES}

    def rep(m):
        target = m.group(1).split("#")[0]
        stem = target[:-5] if target.endswith(".html") else None
        return m.group(2) if stem in slugs and stem not in ready else m.group(0)
    return re.sub(r'<a href="([^"]+)">(.*?)</a>', rep, text, flags=re.S)


def write_page(page, prev_p, next_p, ready):
    slug, code, title, part, _ = page
    meta, body = build.parse_source(SRC / f"{slug}.html")
    body = build.add_abbr(unlink_unwritten(body, ready))
    meta = {k: unlink_unwritten(v, ready) for k, v in meta.items()}
    toc = "\n".join(f'    <li><a href="#{sid}"><span class="n">{html.escape(num)}</span>{html.escape(html.unescape(short or plain(label)))}</a></li>'
                    for sid, short, num, label in TOC_RE.findall(body))
    nav = []
    if prev_p:
        nav.append(f'<a class="pagenav__prev" href="{prev_p[0]}.html"><span>Previous in the syllabus</span>{prev_p[1]} {html.escape(prev_p[2])}</a>')
    if next_p:
        nav.append(f'<a class="pagenav__next" href="{next_p[0]}.html"><span>Next in the syllabus</span>{next_p[1]} {html.escape(next_p[2])}</a>')
    pagenav = f'  <nav class="pagenav" aria-label="Other pages">\n    {"".join(nav)}\n  </nav>\n' if nav else ""
    up = "../"
    out = build.HEAD.format(title=html.escape(f"{code} {meta['title']}"), description=html.escape(meta["description"]), up=up)
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
      <p class="crumbs"><a href="../index.html">Home</a> › <a href="index.html">{SITE_NAME}</a> › {PART_CRUMB[part]} › {meta['crumb']}</p>
      <h1><span class="h1code">{code}</span>{meta['h1']}</h1>
      <p class="lede">{build.add_abbr(meta['lede'])}</p>

      <div class="casesheet">
        <dl>
          <div class="row"><dt>Syllabus</dt><dd>{build.add_abbr(meta['syllabus'])}</dd></div>
          <div class="row"><dt>Priority</dt><dd>{meta['priority']}</dd></div>
          <div class="row"><dt>Asked as</dt><dd>{meta['asked']}</dd></div>
          <div class="row"><dt>Usual split</dt><dd>{meta['split']}</dd></div>
          <div class="row"><dt>Checked against</dt><dd>{build.add_abbr(meta['checked'])}</dd></div>
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
    (OUT / f"{slug}.html").write_text(out, encoding="utf-8")
    return meta


def write_index(ready, metas):
    jump, sections = [], []
    for key, title, hours in PARTS:
        rows = []
        for slug, code, ptitle, part, note in PAGES:
            if part != key:
                continue
            if slug in ready:
                meta_line = plain(metas[slug]["priority"])
                rows.append(f'        <li><span class="syl-code">{html.escape(code)}</span><div><a href="{slug}.html">{html.escape(ptitle)}</a>'
                            f'<span class="meta">{html.escape(meta_line)}</span></div></li>')
            else:
                rows.append(f'        <li><span class="syl-code">{html.escape(code)}</span><div><span class="syl-ttl">{html.escape(ptitle)}</span>'
                            f' <span class="status status--soon">Coming</span><span class="meta">{html.escape(note)}</span></div></li>')
        anchor = f"part-{key.lower()}"
        jump.append(f'<a href="#{anchor}">{key}</a>')
        coded = "" if key.isdigit() else " n--code"
        sections.append(f"""    <section class="sec syl-ch" id="{anchor}">
      <h2><span class="n{coded}">{key}</span>{html.escape(title)}</h2>
      <p class="meta-line">{html.escape(hours)}</p>
      <ol class="syl-items">
{chr(10).join(rows)}
      </ol>
    </section>""")
    out = build.HEAD.format(title="Neuro Physiotherapy notes",
                            description="MUHS final-year BPTh Neuro Physiotherapy notes in the order of the 2012 syllabus, built from the 2016–2026 papers.",
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
      <h1>Neuro Physiotherapy, in syllabus order</h1>
      <p class="lede">Every chapter of the MUHS Neuro Physiotherapy syllabus in its own order, so you can follow your classes. Each page is built from the 20 papers from Summer 2016 to Summer 2026. {(f'All {len(PAGES)} pages are ready.' if len(ready) == len(PAGES) else f'{len(ready)} of {len(PAGES)} pages {"is" if len(ready) == 1 else "are"} ready; the rest are being written in order of how often they are asked.')}</p>
      <nav class="syl-jump" aria-label="Parts">{"".join(jump)}</nav>
    </div>
  </div>

  <div class="wrap">
    <section class="sec" id="how">
      <h2><span class="n">?</span>How to use these notes</h2>
      <ol>
        <li><strong>Follow your classes.</strong> Open the chapter your college is teaching.</li>
        <li><strong>Read a page once</strong>, slowly. Open every "Why?" button.</li>
        <li><strong>Close it and recall.</strong> Write the keywords and draw the diagrams on paper from memory, then compare.</li>
        <li><strong>Test yourself</strong> with the questions at the end of the page. Answer before you open the answer.</li>
        <li><strong>Come back</strong> on day 1, day 7 and day 21, and tick the boxes at the top of the page.</li>
      </ol>
      <div class="note note--exam">
        <span class="note__label">What the real paper looks like (20 papers, 2016–2026)</span>
        <p>80 marks in 3 hours. <strong>No MCQs</strong>, even though the syllabus printed a scheme with them.</p>
        <ul>
          <li>Short answers: any 5 of 6 at <strong>3 marks</strong>, and any 5 of 6 at <strong>7 marks</strong>.</li>
          <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. Every option is a patient case (stroke, cerebral palsy, spinal cord injury, GBS, Parkinson's, MS, DMD, nerve injuries), and almost all ask for ICF and goals.</li>
        </ul>
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


def main():
    build.ABBR = {**build.ABBR, **NEURO_ABBR}
    OUT.mkdir(exist_ok=True)
    ready = ready_pages()
    metas = {}
    for i, page in enumerate(ready):
        metas[page[0]] = write_page(page, ready[i - 1] if i else None, ready[i + 1] if i + 1 < len(ready) else None,
                                    {p[0] for p in ready})
    write_index({p[0] for p in ready}, metas)
    print(f"built {len(ready)} of {len(PAGES)} Neuro pages: {', '.join(p[0] for p in ready) or 'none yet'}")


if __name__ == "__main__":
    main()
