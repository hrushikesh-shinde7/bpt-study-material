#!/usr/bin/env python3
"""Build the printable A4 short notes for CVR.

Each sheet lives in src/cvr/short/<slug>.html, with the same slug as the
full page it condenses: a small metadata comment (pages: the page budget,
title: optional) followed by the sheet's boxes. This script adds a cover,
a how-to page, contents and abbreviations, prints on each sheet the page of
that topic in the full-notes PDF, and renders everything twice with
headless Chrome so the contents carry real page numbers.

Build the full notes first (tools/print_pdf.py), then:

    python tools/print_short.py [output.pdf]

Inside a sheet, <a href="#slug">text</a> becomes "text (p. N)" pointing at
that sheet.
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

SHORT = build.SRC / "cvr" / "short"
OUT_DEFAULT = build.ROOT.parent / "PDF" / "CVR Physiotherapy - short notes (print).pdf"
FOOTER = "CVR Physiotherapy short notes, MUHS IV BPTh"
EXTRA = [("numbers", "Numbers to know")]   # end sheets that are not condensed pages

# Abbreviations the sheets use beyond the site-wide list (build.ABBR)
SHORT_ABBR = {
    "AACVPR": "American Association of Cardiovascular and Pulmonary Rehabilitation", "AARC": "American Association for Respiratory Care",
    "ACC": "American College of Cardiology", "ACE": "Angiotensin-converting enzyme", "ACEi": "ACE inhibitor",
    "ACPRC": "Association of Chartered Physiotherapists in Respiratory Care", "ACS": "Acute coronary syndrome",
    "ACSM": "American College of Sports Medicine", "ACT": "Asthma Control Test", "AD": "Autogenic drainage",
    "ADA": "American Diabetes Association", "AED": "Automated external defibrillator", "AF": "Atrial fibrillation",
    "AHA": "American Heart Association", "AMPPRO": "Amputee Mobility Predictor (with prosthesis)",
    "AP": "Anteroposterior (X-ray view; chest diameter)", "AQLQ": "Asthma Quality of Life Questionnaire",
    "ARB": "Angiotensin receptor blocker", "AS": "Aortic stenosis", "ASD": "Atrial septal defect",
    "ATP": "Adenosine triphosphate", "ATS": "American Thoracic Society", "AV": "Atrioventricular",
    "BC": "Breathing control", "BiPAP": "Bilevel positive airway pressure", "BLS": "Basic life support",
    "BNP": "Brain natriuretic peptide", "BTS": "British Thoracic Society",
    "CAAT": "Chronic Airways Assessment Test (formerly the COPD Assessment Test, CAT)",
    "CF": "Cystic fibrosis", "CFTR": "Cystic fibrosis transmembrane conductance regulator (gene and protein)",
    "CMV": "Controlled mandatory ventilation", "CO": "Carbon monoxide (also cardiac output)",
    "COLS": "Compression-only life support", "CP": "Cerebral palsy (also creatine phosphate)",
    "CPET": "Cardiopulmonary exercise test", "CPP": "Cerebral perfusion pressure (MAP − ICP)",
    "CPR": "Cardiopulmonary resuscitation", "CR10": "Borg category–ratio 0–10 scale", "CSF": "Cerebrospinal fluid",
    "CT": "Computed tomography", "CTR": "Cardiothoracic ratio", "D2": "Diagonal 2 (PNF pattern)",
    "DKA": "Diabetic ketoacidosis", "DLCO": "Diffusing capacity of the lung for carbon monoxide",
    "DNR": "Do not resuscitate", "EDV": "End-diastolic volume", "EIB": "Exercise-induced bronchoconstriction",
    "EPP": "Equal pressure point", "ER": "External rotation", "ERAS": "Enhanced recovery after surgery",
    "ERS": "European Respiratory Society", "ERV": "Expiratory reserve volume", "ESC": "European Society of Cardiology",
    "EVD": "External ventricular drain", "FeNO": "Fractional exhaled nitric oxide", "FET": "Forced expiration technique",
    "GCS": "Glasgow Coma Scale", "GINA": "Global Initiative for Asthma",
    "GOLD": "Global Initiative for Chronic Obstructive Lung Disease", "HADS": "Hospital Anxiety and Depression Scale",
    "HDL": "High-density lipoprotein (good cholesterol)", "HF": "Heart failure",
    "HFrEF": "Heart failure with reduced ejection fraction", "HRmax": "Maximum heart rate", "HRR": "Heart-rate reserve",
    "ICD": "Implantable cardioverter-defibrillator; on the lung surgery and pleural sheets, intercostal (chest) drain",
    "ICS": "Inhaled corticosteroid", "IMAs": "Internal mammary arteries", "IMT": "Inspiratory muscle training",
    "INR": "International normalised ratio (warfarin control)", "IPF": "Idiopathic pulmonary fibrosis",
    "IPV": "Intrapulmonary percussive ventilation", "IRV": "Inspiratory reserve volume",
    "ISH": "International Society of Hypertension", "LA": "Left atrium", "LABA": "Long-acting β2-agonist",
    "LAMA": "Long-acting muscarinic antagonist", "LDH": "Lactate dehydrogenase", "LDL": "Low-density lipoprotein",
    "LOPS": "Loss of protective sensation", "LTOT": "Long-term oxygen therapy", "LV": "Left ventricle",
    "LVH": "Left ventricular hypertrophy", "MCID": "Minimal clinically important difference",
    "MEP": "Maximal expiratory pressure", "MIP": "Maximal inspiratory pressure (PImax)",
    "MODS": "Multiple organ dysfunction syndrome", "MR": "Mitral regurgitation", "MRC": "Medical Research Council (strength grades)",
    "MS": "Mitral stenosis (also multiple sclerosis)", "NG": "Nasogastric",
    "NMES": "Neuromuscular electrical stimulation", "NSAIDs": "Non-steroidal anti-inflammatory drugs",
    "NSTEMI": "Non-ST-elevation myocardial infarction", "NTEP": "National Tuberculosis Elimination Programme (India)",
    "PA": "Posteroanterior (X-ray view); pulmonary artery", "PAQLQ": "Paediatric Asthma Quality of Life Questionnaire",
    "PCF": "Peak cough flow", "PDA": "Patent ductus arteriosus", "PEF": "Peak expiratory flow", "PFO": "Patent foramen ovale",
    "PImax": "Maximal inspiratory pressure", "PND": "Paroxysmal nocturnal dyspnoea",
    "PPCs": "Post-operative pulmonary complications", "PROM": "Passive range of motion", "PS": "Pressure support",
    "PTB": "Pulmonary tuberculosis", "PTCA": "Percutaneous transluminal coronary angioplasty",
    "QoL": "Quality of life", "QRS": "QRS complex (ventricular depolarisation on the ECG)",
    "RA": "Right atrium", "RCA": "Right coronary artery", "RH": "Relative humidity", "RHD": "Rheumatic heart disease",
    "RLL": "Right lower lobe", "RSBI": "Rapid shallow breathing index", "RV": "Residual volume (also right ventricle)",
    "RVH": "Right ventricular hypertrophy", "SA": "Sinoatrial", "SABA": "Short-acting β2-agonist",
    "SACH": "Solid ankle cushion heel (prosthetic foot)", "SBT": "Spontaneous breathing trial", "SCI": "Spinal cord injury",
    "SFJ": "Saphenofemoral junction", "SGLT2": "Sodium–glucose co-transporter 2", "SIGAM": "Special Interest Group in Amputee Medicine (mobility grades)",
    "SMART": "Specific, measurable, achievable, relevant, time-bound", "SMI": "Sustained maximal inspiration",
    "SOAP": "Subjective, objective, assessment, plan", "SOFA": "Sequential Organ Failure Assessment score",
    "STEMI": "ST-elevation myocardial infarction", "SV": "Stroke volume",
    "TAVI": "Transcatheter aortic valve implantation", "TEE": "Thoracic expansion exercises", "TLC": "Total lung capacity",
    "TOF": "Tetralogy of Fallot", "TV": "Tidal volume", "UVC": "Ultraviolet C", "VATS": "Video-assisted thoracoscopic surgery",
    "VC": "Vital capacity", "VF": "Ventricular fibrillation", "VO₂": "Oxygen uptake", "VSD": "Ventricular septal defect",
    "VT": "Tidal volume on the ventilator sheets; ventricular tachycardia on the ECG sheets", "WHO": "World Health Organization",
}

SHORT_CSS = """
@page { size: A4; }
html { font-size: 8.6pt; }
body.print { background: #fff; margin: 0; line-height: 1.3; }
.pm { font-size: 1px; line-height: 0; color: #fff; }
a { color: inherit; text-decoration: none; }
abbr[title] { text-decoration: none; }
.pref { color: var(--ink-2); font-size: 0.92em; white-space: nowrap; font-variant-numeric: tabular-nums; }
.front, .toc-print, .sheet, .abbr-list { break-before: page; }

.cover { height: 255mm; display: flex; flex-direction: column; justify-content: space-between; padding: 20mm 6mm 0; }
.cover__kicker { font-size: 11pt; color: var(--ink-2); margin: 0; }
.cover h1 { font-family: var(--font-head); font-size: 30pt; line-height: 1.12; margin: 6mm 0 4mm; }
.cover__sub { font-size: 13pt; margin: 0 0 10mm; max-width: 140mm; }
.cover__trace { width: 100%; height: 14mm; }
.cover__trace path { fill: none; stroke: var(--ecg-trace); stroke-width: 1.4; vector-effect: non-scaling-stroke; }
.cover dl { display: grid; grid-template-columns: 38mm 1fr; gap: 2mm 6mm; font-size: 10pt; margin: 0; }
.cover dt { font-weight: 700; color: var(--ink-2); }
.cover dd { margin: 0; }
.cover__foot { font-size: 8.5pt; color: var(--ink-2); border-top: 1px solid var(--rule); padding-top: 3mm; }

.front { font-size: 9.6pt; line-height: 1.4; }
.front h1, .toc-print h1, .abbr-list h1 { font-family: var(--font-head); font-size: 17pt; margin: 0 0 3mm; }
.front h2 { font-family: var(--font-head); font-size: 12pt; margin: 5mm 0 2mm; }
.front ol { padding-left: 5mm; }
.front li { margin: 0 0 1.2mm; }
.key { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5mm 6mm; }
.key .b { margin: 0; }
.front .ask { margin-top: 5mm; font-size: 9.2pt; }

.toc-cols { columns: 2; column-gap: 8mm; }
.toc-part { font-family: var(--font-head); font-weight: 700; font-size: 10.5pt; margin: 2.6mm 0 0.6mm; break-after: avoid; }
.toc-part:first-child { margin-top: 0; }
.toc-group { font-weight: 700; font-size: 8.2pt; color: var(--ink-2); margin: 1.8mm 0 0.4mm; break-after: avoid; }
.toc-row { display: flex; align-items: baseline; gap: 1.5mm; font-size: 8.6pt; margin: 0.35mm 0; break-inside: avoid; }
.toc-row .lead { flex: 1; border-bottom: 1px dotted #9aa6b2; transform: translateY(-0.8mm); min-width: 4mm; }
.toc-row .pg { font-variant-numeric: tabular-nums; min-width: 6mm; text-align: right; }

.sh { border-bottom: 2px solid var(--ink); padding-bottom: 1.3mm; margin-bottom: 2.2mm; }
.sh__top { display: flex; justify-content: space-between; align-items: baseline; gap: 4mm; font-size: 7.8pt; color: var(--ink-2); }
.sh__top p { margin: 0; }
.sh__rev i { display: inline-block; width: 2.8mm; height: 2.8mm; border: 1px solid var(--ink-2); border-radius: 0.5mm; margin-left: 1.1mm; vertical-align: -0.5mm; }
.sh h1 { font-family: var(--font-head); font-size: 14.5pt; line-height: 1.15; margin: 0.8mm 0 0.6mm; }
.sh__meta { display: flex; justify-content: space-between; align-items: baseline; gap: 4mm; margin: 0; font-size: 8pt; }
.sh__meta .full { color: var(--ink-2); white-space: nowrap; }

.sn { columns: 2; column-gap: 5.5mm; }
.ask { column-span: all; margin: 0 0 2.4mm; padding: 1.1mm 2.2mm; background: #fff8cc; border-left: 3px solid var(--exam-bar); font-size: 8.2pt; }
.b { margin: 0 0 2.2mm; padding-left: 2.2mm; border-left: 2px solid var(--rule); }
.b > h3 { font-family: var(--font-body); font-size: 9pt; font-weight: 700; line-height: 1.2; margin: 0 0 0.6mm; break-after: avoid; }
.b h4 { font-size: 8.6pt; margin: 1.2mm 0 0.3mm; break-after: avoid; }
.b--p { border-left-color: var(--problem-fill); } .b--p > h3 { color: var(--problem); }
.b--a { border-left-color: var(--action-fill); } .b--a > h3 { color: var(--action); }
.b--c { border-left-color: var(--caution-fill); } .b--c > h3 { color: var(--caution); }
.b--n { border-left-color: var(--normal-fill); } .b--n > h3 { color: var(--normal); }
.b--x { border-left: 3px solid var(--exam-bar); background: #fffbe3; padding: 1.2mm 2mm 0.6mm 2.2mm; }
.b p { margin: 0 0 1mm; }
.b ul, .b ol { margin: 0 0 1mm; padding-left: 3.4mm; }
.b li { margin: 0 0 0.45mm; break-inside: avoid; }
.b li::marker { color: var(--ink-2); }
.b p, .t tr { break-inside: avoid; }
.t { width: 100%; border-collapse: collapse; font-size: 7.8pt; line-height: 1.25; margin: 0.4mm 0 1.2mm; }
.t th, .t td { text-align: left; vertical-align: top; padding: 0.45mm 1.2mm 0.45mm 0; border-bottom: 1px solid var(--rule); }
.t thead th { border-bottom: 1.4px solid var(--ink); color: var(--ink-2); }
.t tbody th { font-weight: 700; }
.hook { font-family: var(--font-head); font-weight: 700; font-size: 12pt; margin: 0.4mm 0 0.2mm; }
.wide { column-span: all; }

.abbr-cols { columns: 3; column-gap: 6mm; font-size: 7.4pt; line-height: 1.25; }
.abbr-cols p { margin: 0 0 0.6mm; break-inside: avoid; }
"""


def esc(s):
    return html.escape(s, quote=True)


def parse(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\s*<!--(.*?)-->\s*(.*)\Z", text, re.S)
    if not m:
        sys.exit(f"{path}: missing metadata comment")
    meta = {}
    for line in m.group(1).strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).rstrip() + "\n"


def sheets():
    """(part, group, slug, title, budget, body) for every written sheet, in book order."""
    order = [(part, group, slug, title) for part, group, _, slug, title in pp.page_list()]
    order += [("E", "End sheets", slug, title) for slug, title in EXTRA]
    out = []
    for part, group, slug, title in order:
        f = SHORT / f"{slug}.html"
        if f.exists():
            meta, body = parse(f)
            out.append((part, group, slug, meta.get("title", title), int(meta.get("pages", "1")), body))
    return out


def full_notes_pages():
    """Printed page of each topic in the full-notes PDF ({} if that PDF is missing)."""
    pdf = pp.OUT_DEFAULT
    if not pdf.exists():
        print("note: full-notes PDF not found, so sheets will not show its page numbers")
        return {}
    sources = [p for p in (build.SRC / "cvr").rglob("*.html") if "short" not in p.parts]
    if pdf.stat().st_mtime < max(p.stat().st_mtime for p in sources):
        print("warning: the full-notes PDF is older than the page sources; rebuild it first so page numbers match")
    doc = pp.Doc()
    pp.build_html(doc, pp.page_list())
    found = pp.page_numbers(pdf, doc)
    return {a[: -len("--top")]: n - 1 for a, n in found.items() if a.endswith("--top")}   # page 1 is the cover


def link_sheets(body, known):
    def rep(m):
        slug, text = m.group(1), m.group(2)
        if slug not in known:
            return text
        return f'<a class="xref">{text}</a>{pp.Doc.pref(slug + "--top")}'
    return re.sub(r'<a href="#([a-z0-9-]+)">(.*?)</a>', rep, body, flags=re.S)


def build_html(doc, items, full_pages):
    head = f"""<!doctype html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<title>Cardio-Vascular and Respiratory Physiotherapy: short notes</title>
<link rel="stylesheet" href="{(build.ROOT / "assets" / "notes.css").as_uri()}">
<style>{SHORT_CSS}</style>
</head>
<body class="print">
"""
    notes = {t[0]: t[3] for t in build.TOPICS + build.CARDS}
    tiers = {t[0]: t[1] for t in build.TOPICS}
    known = {slug for _, _, slug, _, _, _ in items}

    cover = f"""<section class="cover">
  <div>
    <p class="cover__kicker">MUHS final-year BPTh (IV BPTh), 2012 syllabus</p>
    <h1>Cardio-Vascular and Respiratory Physiotherapy</h1>
    <p class="cover__sub">Short notes for revision: one sheet per topic, with the page of the full notes for each.</p>
    <svg class="cover__trace" viewBox="0 0 1000 14" preserveAspectRatio="none" aria-hidden="true"><path d="{build.TRACE}"/></svg>
  </div>
  <dl>
    <dt>Sheets</dt><dd>{len(items)} sheets: the 23 Chapter 6 conditions, the technique cards, the other syllabus chapters and exam skills</dd>
    <dt>Built from</dt><dd>The full notes and 20 MUHS question papers, Summer 2016 to Summer 2026 (code 51413)</dd>
    <dt>Content checked</dt><dd>{pp.DATE}</dd>
    <dt>Online version</dt><dd>{pp.SITE_URL}</dd>
  </dl>
  <p class="cover__foot">Educational notes for exam preparation. Not medical advice. Sources for every fact are listed in the full notes.</p>
</section>"""

    front = f"""<section class="front" id="front--top">{doc.marker("front--top")}
  <h1>How to use the short notes</h1>
  <p>These sheets are for revision, after you have read a topic once in the full notes. Each topic has its own sheet of one to three pages, in the same order as the full notes, and the last sheet collects the numbers to know.</p>
  <ol>
    <li><b>Read the yellow line first.</b> It says how the topic is asked in the MUHS paper.</li>
    <li><b>Cover a box and recall it,</b> then check. Bold words and numbers are the ones to write in the answer.</li>
    <li><b>Tick a square at the top right of a sheet</b> each time you revise it. Aim for day 1, day 7 and day 21.</li>
    <li><b>Need more?</b> Each sheet gives the page of the same topic in the full notes.</li>
  </ol>
  <h2>What the colours mean</h2>
  <div class="key">
    <section class="b"><h3>Grey</h3><p>Definitions, types, medical and surgical management</p></section>
    <section class="b b--p"><h3>Orange</h3><p>Disease process, clinical features and the problems they cause</p></section>
    <section class="b b--n"><h3>Blue</h3><p>Investigations, scales and normal values</p></section>
    <section class="b b--a"><h3>Green</h3><p>Physiotherapy: assessment, ICF, goals, treatment and doses</p></section>
    <section class="b b--c"><h3>Amber</h3><p>Precautions, contraindications, stop criteria and complications</p></section>
    <section class="b b--x"><h3>Yellow</h3><p>Exam plan: answer structure, what to draw, keywords</p></section>
  </div>
  <p class="ask"><b>The paper (20 papers, 2016–2026):</b> 80 marks in 3 hours, no MCQs. Short answers: any 5 of 6 at 3 marks and any 5 of 6 at 7 marks. Long answers: two questions, each any 1 of 2 at 15 marks, always a patient case, almost always asking ICF, a functional diagnosis or impairments. Since 2023 a ventilated ICU patient appears as a long case and an ICU short question is in every paper.</p>
</section>"""

    toc = ['<section class="toc-print">', "  <h1>Contents</h1>", '  <div class="toc-cols">']
    cur_part, cur_group = None, None
    for part, group, slug, title, _, _ in items:
        if part != cur_part:
            name = next((p[1] for p in pp.PARTS if p[0] == part), "End sheets")
            label = f"Part {part}: {name}" if part != "E" else name
            toc.append(f'  <p class="toc-part">{esc(label)}</p>')
            cur_part, cur_group = part, None
        if group != cur_group and part != "E":
            toc.append(f'  <p class="toc-group">{esc(group)}</p>')
            cur_group = group
        toc.append("  " + pp.toc_row(title, slug + "--top"))
    toc.append("  " + pp.toc_row("Abbreviations", "abbr--top"))
    toc += ["  </div>", "</section>"]

    out = [front, "\n".join(toc)]
    for part, group, slug, title, budget, body in items:
        if slug in tiers:
            crumb = f"Chapter 6, Tier {tiers[slug]}"
        elif part == "E":
            crumb = "End sheet"
        else:
            crumb = group
        full = f'<span class="full">Full notes p.&nbsp;{full_pages[slug]}</span>' if slug in full_pages else ""
        meta_line = f'<p class="sh__meta"><span>{esc(notes.get(slug, ""))}</span>{full}</p>' if notes.get(slug) or full else ""
        out.append(f"""<article class="sheet" id="{slug}--top" data-budget="{budget}">{doc.marker(slug + "--top")}
  <header class="sh">
    <div class="sh__top"><p>{esc(crumb)}</p><p class="sh__rev">Revised<i></i><i></i><i></i></p></div>
    <h1>{esc(title)}</h1>
    {meta_line}
  </header>
  <div class="sn">
{link_sheets(body, known)}  </div>
</article>""")

    items_ab = sorted({**SHORT_ABBR, **build.ABBR}.items(), key=lambda kv: kv[0].lower())
    abbr = [f'<section class="abbr-list" id="abbr--top">{doc.marker("abbr--top")}', "  <h1>Abbreviations</h1>",
            '  <div class="abbr-cols">']
    abbr += [f"    <p><b>{esc(k)}</b>: {esc(v)}</p>" for k, v in items_ab]
    abbr += ["  </div>", "</section>"]
    out.append("\n".join(abbr))
    return head + "\n".join(out) + "\n</body>\n</html>\n", head + cover + "\n</body>\n</html>\n"


def budget_report(numbers, items):
    """Sheets that run over their page budget."""
    starts = [(numbers.get(f"{slug}--top"), slug, budget) for _, _, slug, _, budget, _ in items]
    ends = [s for s, _, _ in starts[1:]] + [numbers.get("abbr--top")]
    over = []
    for (start, slug, budget), nxt in zip(starts, ends):
        if start and nxt and nxt - start > budget:
            over.append(f"{slug} ({nxt - start} pages, budget {budget})")
    return over


def main():
    out_pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    items = sheets()
    if not items:
        sys.exit(f"no sheets found in {SHORT}")
    full_pages = full_notes_pages()
    doc = pp.Doc()
    body_html, cover_html = build_html(doc, items, full_pages)
    work = Path(tempfile.mkdtemp(prefix="cvr-short-"))
    body_file, cover_file = work / "body.html", work / "cover.html"
    cover_file.write_text(cover_html, encoding="utf-8")
    body_file.write_text(body_html, encoding="utf-8")
    chrome = pp.Chrome()
    try:
        chrome.load(body_file.as_uri())
        chrome.pdf(work / "pass1.pdf", footer_text=FOOTER)
        numbers = pp.page_numbers(work / "pass1.pdf", doc)
        final_html, missing = pp.fill(body_html, numbers)
        if missing:
            print(f"warning: no page found for {len(missing)} anchors, e.g. {sorted(missing)[:5]}")
        body_file.write_text(final_html, encoding="utf-8")
        chrome.load(body_file.as_uri())
        chrome.pdf(work / "body.pdf", footer_text=FOOTER)
        check = pp.page_numbers(work / "body.pdf", doc)
        moved = [a for a in numbers if check.get(a) != numbers[a]]
        if moved:
            print(f"warning: {len(moved)} anchors moved between passes, e.g. {moved[:5]}")
        chrome.load(cover_file.as_uri())
        chrome.pdf(work / "cover.pdf", footer=False)
    finally:
        chrome.close()
    subprocess.run(["pdfunite", str(work / "cover.pdf"), str(work / "body.pdf"), str(out_pdf)], check=True)
    over = budget_report(check, items)
    if over:
        print(f"over budget: {', '.join(over)}")
    info = subprocess.run(["pdfinfo", str(out_pdf)], capture_output=True, text=True).stdout
    pages_line = next((l for l in info.splitlines() if l.startswith("Pages:")), "")
    print(f"wrote {out_pdf} ({pages_line.split()[-1] if pages_line else '?'} pages, "
          f"{out_pdf.stat().st_size / 1e6:.1f} MB); {len(items)} sheets")
    print(f"work files: {work}")


if __name__ == "__main__":
    main()
