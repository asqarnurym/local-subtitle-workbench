# IEEE DG conference templates

Copied on 13.11.2026 from `C:\Users\nurym\Desktop\Prototype\template` (Prototype repo, last change to the folder 10.08.2026). The originals stay in the Prototype folder.

These are the **IEEE DG 2026** files used for the first paper (Paper 15). The 2027 versions are not published yet. Before submitting, check on https://sc.astanait.edu.kz whether the requirements or the template changed.

| File | Purpose |
|---|---|
| `IEEE-conference-template-062824.tex` | Official IEEE conference LaTeX template (version 27.06.2024), `\documentclass[conference]{IEEEtran}` |
| `IEEEtran.cls`, `IEEEtran.bst`, `IEEEabrv.bib` | Class, bibliography style and journal abbreviations for the template |
| `IEEE-DG-2026-paper-requirements.doc` | Conference requirements (Word template with the rules) |
| `TEMPLATE-FOR-PRESENT-STUD-CONFERENCE-2026-1.pptx` | Presentation template for the talk (needed only after acceptance) |

Not copied: `IEEEexample.bib`, `IEEEfull.bib`, `IEEEtranS.bst`, `fig1.png`, the bst `README`. These are template examples and alternative styles we do not need.

## Requirements (DG 2026 document)

- Camera-ready paper of **4–6 pages**, English only, A4. Submitted through Microsoft CMT.
- No symbols, special characters or math in the title and abstract.
- Do not change margins, columns or fonts. Do not number headings by hand, and do not add page numbers.
- Up to 6 author blocks; an e-mail is required, ORCID is optional.
- The paper must state the scope of the work and the new advances, and analyse results, so the committee can see originality and value.

## Lessons from the DG 2026 submission (Prototype)

- A blind version was prepared (`academic_paper/main_blind.tex`, `paper_blind.tex`). Plan for an anonymised copy as well.
- The first page header was set by hand in `paper.tex`: `2026 IEEE 3rd International Student Conference on Digital Generation`, the dates and Astana. For 2027 the header becomes the 4th conference, 24–26 February 2027.
- The university ran a Strikeplagiarism check on the text, including an AI-content indicator. The 2026 drafts got AI indicators of 64–100% and had to be rewritten by hand (`Prototype/strikeplagiarism_audit.md`). Write the text yourself from the start, and check the final blind PDF with a fresh run.
