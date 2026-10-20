#!/usr/bin/env python3
"""Build the Community Physiotherapy notes into community/.

The pages follow the MUHS 2012 Community Physiotherapy syllabus: 1 health
promotion, 2 women's health, 3 geriatrics, 4 concepts of rehabilitation,
5 disaster management, 6 industrial health, 7 the project synopsis, then
exam skills.

Each page's source is src/community/<slug>.html: a metadata comment followed
by <section class="sec"> blocks, in the same format as the other subjects
(STYLE.md). Pages without a source yet appear on the contents page as "Coming".

Run from anywhere:  python3 tools/build_community.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  shared frame, abbreviations, metadata parser

ROOT = build.ROOT
SRC = build.SRC / "community"
OUT = ROOT / "community"
SITE_NAME = "Community Physiotherapy"

# Parts of the syllabus, in order: key, title, hours or note.
PARTS = [
    ("1", "Health promotion", "10 hours theory, 15 field"),
    ("2", "Women's health", "20 hours theory, 20 field"),
    ("3", "Geriatrics", "20 hours theory, 20 field"),
    ("4", "Concepts of rehabilitation", "11 hours theory, 20 field"),
    ("5", "Disaster management", "2 hours theory"),
    ("6", "Industrial health", "20 hours theory, 20 field"),
    ("7", "Project synopsis", "20 field hours; 25 practical marks"),
    ("E", "Exam skills", "How the notes become marks"),
]

# Pages in syllabus order: slug, syllabus code, title, part, note shown on the contents page until the page is written.
PAGES = [
    ("1-health-delivery", "1(a, b)", "Health, disease and the health care delivery system in India", "1", "9 papers: WHO definition, the three tiers, PHC, scope of community physiotherapy."),
    ("1c-fitness", "1(c)", "Physical fitness: components, evaluation and exercise prescription", "1", "12 papers: FITT, aerobic and anaerobic exercise, MET, field tests, bed rest."),
    ("1c-obesity", "1(c)", "Obesity in children and adults: body composition, BMI and weight management", "1", "14 papers, with 10 long cases on weight reduction."),
    ("2a-women-india", "2(a–c)", "Women in India: social issues, legal rights and health promotion", "2", "5 papers: social issues, legal rights, rural women."),
    ("2d-pregnancy", "2(d, e)", "Pregnancy: physiological changes, discomforts and antenatal care", "2", "13 papers: changes in pregnancy, diastasis recti, exercise guidelines."),
    ("2e-labour-postnatal", "2(e)", "Labour and postnatal care", "2", "14 papers, with 9 long cases on labour, caesarean section and postnatal care."),
    ("2d-menopause", "2(d)", "Menopause and osteoporosis", "2", "8 papers: changes at menopause, osteoporosis."),
    ("2f-pelvic-floor", "2(f)", "Urogenital dysfunction: incontinence, prolapse and the pelvic floor", "2", "16 papers: incontinence and prolapse cases, PERFECT, Kegel's."),
    ("3a-elderly-india", "3(a–c)", "Senior citizens in India: policies, NGOs, living arrangements and communication", "3", "6 papers: policies, institution vs home, communication barriers."),
    ("3d-aging-theories", "3(d)", "Theories of ageing", "3", "9 papers, mostly 7 marks."),
    ("3e-aging-physiology", "3(e)", "Physiology of ageing and the effects of exercise", "3", "14 papers: changes in each body system and how exercise helps."),
    ("3f-geriatric-evaluation", "3(f)", "Geriatric evaluation and the role of physiotherapy", "3", "9 papers: assessment scales, functional assessment, geriatric rehabilitation."),
    ("3f-falls", "3(f)", "Falls in the elderly", "3", "8 papers, with 5 long cases on fall risk and prevention."),
    ("4a-disability", "4(a)", "Disability: definitions, models, types, evaluation and prevention", "4", "9 papers: impairment, disability and handicap; levels of prevention."),
    ("4b-rehabilitation", "4(b, d)", "Rehabilitation: types, IBR vs CBR and the rehabilitation team", "4", "15 papers: IBR vs CBR, NGOs, social worker, vocational rehabilitation."),
    ("4c-policies", "4(c)", "National policies and legal rights for persons with disability", "4", "7 papers: PWD Act, national programmes, barriers, concessions."),
    ("4e-cbr", "4(e, f)", "Community-based rehabilitation: principles, strategies and the physiotherapist", "4", "11 papers: principles of CBR, the anganwadi worker, rural and urban strategies."),
    ("4-amputee", "4", "Rehabilitation of an amputee in the community", "4", "5 papers: below-knee amputee long cases, prosthetic check-outs."),
    ("5-disaster", "5", "Disaster management", "5", "3 papers: types, principles, the cycle and triage."),
    ("6a-industrial", "6(a)", "Industrial health: models, the team and the worker care spectrum", "6", "3 papers: industrial therapy, role of the physiotherapist, pre-placement."),
    ("6b-ability-management", "6(b i)", "Ability management: job analysis, ergonomics and injury prevention", "6", "10 papers: job and task analysis, ergonomic evaluation, REBA, workstation exercises."),
    ("6b-disability-management", "6(b ii)", "Disability management: functional capacity evaluation, work conditioning and work hardening", "6", "10 papers: FCE, work conditioning, work hardening."),
    ("6c-hazards", "6(b iii)", "Environmental stress at work: physical, chemical and mechanical hazards", "6", "12 papers: vibration, pneumoconiosis, cumulative trauma disorders."),
    ("6d-mechanical-stress", "6(b iv)", "Mechanical and psychological stress at work", "6", "17 papers, with 16 long cases: computer users, drivers, standing workers, labourers."),
    ("7-synopsis", "7", "The project synopsis", "7", "25 practical marks: the synopsis you present and defend."),
    ("exam-theory", "Exam", "Answer writing for the Community paper", "E", "The paper, long cases and answer skeletons."),
    ("exam-practical", "Exam", "The Community practical exam: long case, synopsis and journal", "E", "Long case 50, synopsis 25, journal 5."),
]

PART_CRUMB = {
    "1": "1 Health promotion", "2": "2 Women's health", "3": "3 Geriatrics", "4": "4 Rehabilitation",
    "5": "5 Disaster management", "6": "6 Industrial health", "7": "7 Synopsis", "E": "Exam skills",
}

# Abbreviations for community physiotherapy, added to the shared list.
COMMUNITY_ABBR = {
    "CBR": "Community-based rehabilitation", "IBR": "Institution-based rehabilitation",
    "NGO": "Non-governmental organisation", "PHC": "Primary health centre", "CHC": "Community health centre",
    "ASHA": "Accredited Social Health Activist", "ANM": "Auxiliary nurse midwife", "AWW": "Anganwadi worker",
    "WHO": "World Health Organization", "LBP": "Low back pain", "OA": "Osteoarthritis",
    "FCE": "Functional capacity evaluation", "FCA": "Functional capacity assessment",
    "CTD": "Cumulative trauma disorder", "WMSD": "Work-related musculoskeletal disorder",
    "REBA": "Rapid Entire Body Assessment", "RULA": "Rapid Upper Limb Assessment",
    "HAVS": "Hand–arm vibration syndrome", "CTS": "Carpal tunnel syndrome",
    "PFM": "Pelvic floor muscles", "SUI": "Stress urinary incontinence", "UUI": "Urge urinary incontinence",
    "POP": "Pelvic organ prolapse", "DRA": "Diastasis recti abdominis", "PCOS": "Polycystic ovary syndrome",
    "PCOD": "Polycystic ovarian disease", "FTND": "Full-term normal delivery", "LSCS": "Lower segment caesarean section",
    "TENS": "Transcutaneous electrical nerve stimulation", "IFT": "Interferential therapy",
    "WHR": "Waist–hip ratio", "FITT": "Frequency, intensity, time and type", "VO2max": "Maximal oxygen uptake",
    "PWD": "Persons with disabilities", "RPWD": "Rights of Persons with Disabilities",
    "UDID": "Unique Disability ID", "ADIP": "Assistance to Disabled Persons for purchase of aids and appliances",
    "RCI": "Rehabilitation Council of India", "BPL": "Below poverty line",
    "BMD": "Bone mineral density", "DEXA": "Dual-energy X-ray absorptiometry", "HRT": "Hormone replacement therapy",
    "TUG": "Timed Up and Go test", "BBS": "Berg Balance Scale", "MMSE": "Mini-Mental State Examination",
    "BK": "Below-knee", "AK": "Above-knee", "PTB": "Patellar tendon bearing", "SACH": "Solid ankle cushion heel",
    "MSW": "Medical social worker", "OT": "Occupational therapy", "RTA": "Road traffic accident",
    "PPE": "Personal protective equipment", "NDMA": "National Disaster Management Authority",
}

TOC_RE = re.compile(r'<section class="sec[^"]*" id="([^"]+)"(?: data-toc="([^"]*)")?>\s*<h2><span class="n[^"]*">([^<]*)</span>(.*?)</h2>', re.S)


def plain(h):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()


def ready_pages():
    return [p for p in PAGES if (SRC / f"{p[0]}.html").exists()]


def unlink_unwritten(text, ready):
    """Links to Community pages that are not written yet become plain text until the page exists."""
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
    <a href="index.html">All syllabus parts</a>
  </div>
</nav>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs"><a href="../index.html">Home</a> › <a href="index.html">{SITE_NAME}</a> › {PART_CRUMB[part]} › {meta['crumb']}</p>
      <h1><span class="h1code">{code}</span>{meta['h1']}</h1>
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
    out = build.HEAD.format(title="Community Physiotherapy notes",
                            description="MUHS final-year BPTh Community Physiotherapy notes in the order of the 2012 syllabus, built from the 2016–2026 papers.",
                            up="../")
    out = out.replace('<link rel="stylesheet" href="../assets/notes.css">',
                      '<link rel="stylesheet" href="../assets/notes.css">\n<link rel="stylesheet" href="../assets/syllabus.css">')
    out += f"""<a class="skip" href="#content">Skip to the parts</a>
<header class="topbar">
  <div class="topbar__title">{SITE_NAME}</div>
  {build.THEME_BTN}
</header>

<main id="content">
  <div class="pagehead">
    <div class="wrap">
      <p class="crumbs"><a href="../index.html">Home</a> › {SITE_NAME}</p>
      <h1>Community Physiotherapy, in syllabus order</h1>
      <p class="lede">Every part of the MUHS Community Physiotherapy syllabus in its own order, so you can follow your classes. Each page is built from the 20 papers from Summer 2016 to Summer 2026. {(f'All {len(PAGES)} pages are ready.' if len(ready) == len(PAGES) else f'{len(ready)} of {len(PAGES)} pages {"is" if len(ready) == 1 else "are"} ready; the rest are being written in order of how often they are asked.')}</p>
      <nav class="syl-jump" aria-label="Parts">{"".join(jump)}</nav>
    </div>
  </div>

  <div class="wrap">
    <section class="sec" id="how">
      <h2><span class="n">?</span>How to use these notes</h2>
      <ol>
        <li><strong>Follow your classes.</strong> Open the part your college is teaching.</li>
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
          <li>Long answers: two questions, each any 1 of 2 at <strong>15 marks</strong>. Most options are a person in the community (an office worker with neck pain, a new mother, an older person who falls, an obese teenager, an amputee in a village), and many ask for a functional diagnosis with goals.</li>
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
    build.ABBR = {**build.ABBR, **COMMUNITY_ABBR}
    OUT.mkdir(exist_ok=True)
    ready = ready_pages()
    metas = {}
    for i, page in enumerate(ready):
        metas[page[0]] = write_page(page, ready[i - 1] if i else None, ready[i + 1] if i + 1 < len(ready) else None,
                                    {p[0] for p in ready})
    write_index({p[0] for p in ready}, metas)
    print(f"built {len(ready)} of {len(PAGES)} Community pages: {', '.join(p[0] for p in ready) or 'none yet'}")


if __name__ == "__main__":
    main()
