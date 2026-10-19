# BPTh study notes

Exam notes for MUHS final-year BPTh, starting with the full Cardio-Vascular and Respiratory Physiotherapy syllabus: Chapter 6 conditions (ordered by how often they appear in 20 past MUHS papers, Summer 2016 to Summer 2026), technique cards, the other syllabus chapters (basics, cardiac and pulmonary rehabilitation, ICU conditions, basic life support), and exam skills (answer writing and the practical exam).

Open `index.html` to start. The site is plain HTML, CSS and JavaScript with self-hosted fonts, so it also works offline.

## Structure

- `index.html`: the home page listing every page
- `cvr/ch6/`: one page per condition
- `cvr/cards/`: technique cards, other syllabus chapters and exam-skills pages
- `cvr-syllabus/`: the same notes in the order of the MUHS syllabus (see below)
- `src/`: page sources; `tools/build.py` builds the pages from them
- `src/cvr/short/`, `src/cvr/answers/`: sources for the printable short notes and model answers (not built into the site)
- `src/cvr-syllabus/`: hand-written parts of the syllabus-order version
- `neuro/`: Neuro Physiotherapy notes in syllabus order, built by `tools/build_neuro.py` from `src/neuro/` (pages not yet written show as "Coming")
- `assets/notes.css`, `assets/notes.js`: shared styles and behaviour
- `assets/fonts/`: Atkinson Hyperlegible and Literata (SIL Open Font License)

## Syllabus-order version

`cvr-syllabus/index.html` lists the CVR syllabus in its own order: Chapters 1 to 11 with every lettered and numbered item, then the practical list and exam skills. Each item links to its notes, so a student can follow the order in which the college teaches.

`tools/build_syllabus.py` builds these pages from the topic sources in `src/cvr/`, section by section, so a fix there reaches both versions. The page list and syllabus wording are at the top of the script. Where one topic page covers syllabus items that the syllabus lists apart (valve disease and heart failure; the pleural disorders), the split parts are hand-written in `src/cvr-syllabus/`, and each file names the topic page it came from. These parts must be corrected in both places. The script rewrites links and section numbers for their new pages, and lists any link, anchor or topic section left unplaced:

    python tools/build.py
    python tools/build_syllabus.py

`tools/print_syllabus.py` prints this version as an A4 book: a cover, contents, an opener page for each chapter listing its syllabus items with page numbers, every page, and the abbreviations. It assembles the pages itself and has the same requirements as the complete-notes PDF below:

    python tools/print_syllabus.py [output.pdf]

Without an argument it writes `../PDF/CVR Physiotherapy - syllabus order (print).pdf`.

## Printable PDF

`tools/print_pdf.py` joins every CVR page into one A4 book with a cover, contents, syllabus map, part dividers, page-numbered cross-references and an abbreviations list. It needs Google Chrome, poppler (`pdftotext`, `pdfunite`) and the Python package `websocket-client`:

    python tools/build.py
    python tools/print_pdf.py [output.pdf]

Without an argument it writes `../PDF/CVR Physiotherapy - complete notes (print).pdf`, outside this repository.

## Printable short notes

`src/cvr/short/` holds one revision sheet per topic (same slugs as the full pages), plus a closing "Numbers to know" sheet. Each sheet starts with a small metadata comment giving its page budget. `tools/print_short.py` turns them into an A4 book with a cover, a how-to page, contents and abbreviations, and prints on every sheet the page of that topic in the full-notes PDF, so build the full notes first:

    python tools/print_pdf.py
    python tools/print_short.py [output.pdf]

It reports any sheet that runs over its page budget. Without an argument it writes `../PDF/CVR Physiotherapy - short notes (print).pdf`.

## Printable model answers

`src/cvr/answers/` holds model answers to every 3-mark (Q1) and 7-mark (Q2) question in the MUHS papers from Summer 2016 to Summer 2026, one file per topic (same slugs as the full pages). Each question is an `<article class="qa">` whose `data-marks` is 3 or 7 and whose `data-asked` lists the paper slots it answers (`S17-1b` is Summer 2017, Q1 b). A question asked in several papers has one answer listing them all. Inside an answer, `<div class="figref" data-fig="cards/acbt#ac1t"></div>` embeds a figure from a full page, and `<a href="#answer-id">` becomes a cross-reference with a page number.

`tools/print_answers.py` turns them into a two-column A4 book with a cover, a how-to page, contents, the answers by topic (each topic with its page in the full-notes PDF), an index by paper and abbreviations. It stops if a paper slot is answered twice and reports any empty answers. Build the full notes first:

    python tools/print_pdf.py
    python tools/print_answers.py [output.pdf]

Without an argument it writes `../PDF/CVR Physiotherapy - 3 and 7 mark answers (print).pdf`.

Educational notes for exam preparation. Not medical advice. Each page lists its sources and the date its content was checked.
