# Style guide for the notes

Reader: Digvijay, final-year BPTh (MUHS, 2012 syllabus), studying only from these pages, mostly on a phone. The design comes from the research report in `Study Material/reports/` (kept locally, not in this repo). The reference page is `src/cvr/ch6/ihd-mi-cabg.html`. When in doubt, copy its patterns.

## Workflow for a page

1. Read the topic's past questions in `Study Material/Past Papers/CVR 51413/question-bank.md` and the relevant research notes.
2. Verify every number that depends on a guideline (thresholds, doses, grades, timings) against the primary document or two independent sources. Unverified numbers are left out, never guessed. Note anything checked only via secondary reproductions in the page's Sources section.
3. Write `src/cvr/ch6/<slug>.html`: a metadata comment, then the `<section class="sec">` blocks, ending with the Sources section.
4. Run `python3 tools/build.py`. This builds the page and updates `index.html`.
5. Check that the HTML parses and that the page looks right at 390 px.
6. Commit with the attribution line and push. GitHub Pages redeploys in about a minute.

## Metadata comment (all keys required)

```
<!--
title: Short browser-tab title
h1: Full page heading
crumb: 6(g) Burns
description: One sentence for search and previews.
lede: Two sentences: why this topic matters in the exam and the routine every answer follows.
syllabus: Ch 6(g) ...
priority: <span class="tier">Tier 1.</span> In N of 12 papers (2016–2022). ...
asked: <span class="chip chip--laq">LAQ S16</span>... <span class="chip chip--7m">7m W16</span>... <span class="chip chip--3m">3m S17</span>...
split: Usual mark splits
checked: Named, dated guidelines and sources
date: 19 October 2026
review: Month Year
-->
```

## Section templates

Tier 1 and Tier 2 use the 16 numbered sections (ids s1–s16, then `sources`). Section numbers mean the same thing on every page:

1 Definition · 2 Classification and grading · 3 Causes and risk factors · 4 Pathophysiology to impairments · 5 Clinical features · 6 Investigations · 7 Medical and surgical management · 8 Complications and prevention · 9 PT assessment · 10 PT diagnosis by ICF · 11 Problem list and goals · 12 PT management · 13 Precautions, contraindications and stop criteria · 14 Education, lifestyle and home programme · 15 Prognosis and discharge criteria · 16 Exam corner

- Section 10 always has: the ICF model figure (or a link to it on the IHD page for Tier 2), a worked ICF table from a real past case with a "Clinical reasoning" column, "Spot the ICF clues", and a one-line functional diagnosis.
- Section 12 always has management by phase AND an impairment → technique and dose → why table.
- Section 16 always has: past questions (cleaned wording, session tags, marks), keywords to underline, an answer skeleton, "Draw these", viva questions, linked practical spots, and a Test yourself block (3m, 7m, LAQ, plus 3–5 MCQs).

Tier 3 pages cover several conditions. Each condition gets seven parts as `<h3>` blocks inside one numbered section per condition: Definition and types · Causes and key features (clinical and X-ray) · Medical or surgical point that matters for PT · ICF summary · PT management by key problem, with doses · Precautions · Exam points. The page ends with a shared exam corner and Sources.

Use `data-toc="Short label"` on a section when its heading is too long for the contents menu.

## Writing rules

- One idea per sentence, mostly 10–20 words. Plain English. Spell out every abbreviation the first time it appears on a page (use `<abbr title>`).
- Use commands for treatment steps ("Position in high side-lying").
- Use "because… so…" sentences for mechanisms. Long answers test cause and effect.
- Bullets for lists; 3–7 bullets per block.
- Use the examiner's words: short-term goals, long-term goals, impairment, activity limitation, participation restriction, facilitator, barrier.
- Give concrete doses, wrapped in `<span class="dose">`.
- Indian context: Indian toilets, stairs with no lift, sole earner, tobacco forms, Indian BMI cut-offs (23 and 25), mg/dL units.
- Where old textbooks and current guidelines disagree, use a classic-vs-current box (`.cvc`) with a "Write in the exam" line. Never present superseded practice as current.
- No middle-dot meta strings, no all-caps labels, no arrow-suffixed links.

## Components (class names)

- Callouts: `.note.note--exam` (exam point), `.note--caution` (do not start / careful), `.note--problem` (stop criteria, danger), `.note--action` (functional diagnosis line), plain `.note`.
- Memory hook: `.hook` with `.hook__label`, `.hook__big`, a list spelling out each part, and `.hook__src` saying what it was checked against. Only for lists of 4–8 items, sequences or number sets, and always placed after the explanation.
- "Why?" reveal: `<details class="why"><summary>Why …?</summary><div>…</div></details>`.
- Tables: `.tbl.tbl--stack` with `data-label` on every `td` so they stack on phones. At most 3 columns.
- Keywords: `<mark>`. Doses and numbers: `<span class="dose">`.
- Recall prompt: `<div class="recall"><strong>Recall check.</strong> …</div>` after sections 4, 10 and 12.
- Self-test: `.selftest` containing `<details class="q"><summary><span class="qtag">3 m</span><span class="qtext">Question</span></summary><div class="a">…</div></details>`. MCQ options go inside `.qtext` as `<span class="mcq-opts"><span>A. …</span>…</span>`.
- Past questions: `<ul class="pq"><li><span class="src">S16 Q3(a), 5 + 10 marks</span>Text</li></ul>`.
- Answer skeleton: `<ol class="skeleton">` with `<span class="marks">[ICF, 5]</span>`.

## Diagrams

- Inline SVG, drawn from scratch (never traced from a book), with `role="img"`, `<title>` and `<desc>`. Use a canvas 360 units wide and as tall as needed.
- Wrap each in `figure.fig` with `.fig__head` (title plus the "Show exam sketch" button `.js-sketch`), `.fig__body`, a `figcaption`, and a `<details>` text version where it is a flowchart.
- Classes: `d-box`, `d-box--problem|action|normal|caution`, `d-text`, `d-small`, `d-bold`, `d-t-problem|action|normal`, `d-line`, `d-line--action`, `d-skin`, `d-cut`, `d-tube`, `d-graft`. Use marker ids unique to the page.
- Mark labels that the 2-minute exam sketch can drop with `d-detail`.
- Colour meanings: vermillion = problem, bluish green = what physio does, blue = normal structure or device, orange = caution. Never rely on colour alone.
- Keep labels at 12.5 px or more in the 360-unit canvas, with 5–7 boxes per view where possible.

## Accuracy and sources

- Each page lists its sources with editions and years, plus "content checked" and "next review" dates.
- Write from current books (Main & Denehy 2016, Frownfelter & Dean 2022, Hillegass 2022, ACSM GETP, Jiandani 2022). Use Cash's and Brompton only for the classical structure.
- Guideline numbers override textbook numbers.
- Write everything in original words. No copied paragraphs, no scanned or traced figures, no GOLD or GINA figures.
