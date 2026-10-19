# BPTh study notes

Exam notes for MUHS final-year BPTh, starting with the full Cardio-Vascular and Respiratory Physiotherapy syllabus: Chapter 6 conditions (ordered by how often they appear in 20 past MUHS papers, Summer 2016 to Summer 2026), technique cards, the other syllabus chapters (basics, cardiac and pulmonary rehabilitation, ICU conditions, basic life support), and exam skills (answer writing and the practical exam).

Open `index.html` to start. The site is plain HTML, CSS and JavaScript with self-hosted fonts, so it also works offline.

## Structure

- `index.html`: the home page listing every page
- `cvr/ch6/`: one page per condition
- `cvr/cards/`: technique cards, other syllabus chapters and exam-skills pages
- `src/`: page sources; `tools/build.py` builds the pages from them
- `src/cvr/short/`, `src/cvr/answers/`: sources for the printable short notes and model answers (not built into the site)
- `assets/notes.css`, `assets/notes.js`: shared styles and behaviour
- `assets/fonts/`: Atkinson Hyperlegible and Literata (SIL Open Font License)

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
