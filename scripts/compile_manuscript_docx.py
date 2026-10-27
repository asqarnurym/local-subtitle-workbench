"""Compile ARTICLE_2_MANUSCRIPT_DRAFT.md into publication-grade Word .docx

Follows Scientific Journal of Astana IT University author formatting guidelines:
- Page: A4 (210 x 297 mm)
- Margins: Top 2.0 cm, Bottom 2.5 cm, Left 3.0 cm, Right 1.5 cm
- Font: Times New Roman
- Size: Title 14pt Bold, Headings 12pt Bold, Body 12pt Regular, Tables/Refs 11pt Regular
- Line spacing: 1.0 (single)
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Pt, RGBColor


def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    """Set custom cell borders."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f"<w:tcBorders {nsdecls('w')}>\n"
        f'  <w:top w:val="{top or "none"}" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:left w:val="{left or "none"}" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:bottom w:val="{bottom or "none"}" w:sz="4" w:space="0" w:color="000000"/>\n'
        f'  <w:right w:val="{right or "none"}" w:sz="4" w:space="0" w:color="000000"/>\n'
        f"</w:tcBorders>"
    )
    tcPr.append(tcBorders)


def compile_manuscript():
    repo_root = Path(__file__).resolve().parent.parent
    md_path = repo_root / "docs" / "paper" / "archive" / "ARTICLE_2_MANUSCRIPT_DRAFT.md"
    if not md_path.exists():
        md_path = repo_root / "docs" / "paper" / "ARTICLE_2_MANUSCRIPT_DRAFT.md"
    docx_path = repo_root / "docs" / "paper" / "archive" / "ARTICLE_2_MANUSCRIPT_AITU.docx"
    if not docx_path.parent.exists():
        docx_path = repo_root / "docs" / "paper" / "ARTICLE_2_MANUSCRIPT_AITU.docx"

    if not md_path.exists():
        raise FileNotFoundError(f"Markdown manuscript not found at {md_path}")

    doc = Document()

    # Configure A4 & Margins
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(1.5)

    # Set base style to Times New Roman
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)
    font.color.rgb = RGBColor(0, 0, 0)
    style.paragraph_format.line_spacing = 1.0
    style.paragraph_format.space_after = Pt(4)
    style.paragraph_format.space_before = Pt(0)

    raw_text = md_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i].rstrip()

        # Handle LaTeX Table insertion points
        if line.startswith(r"\begin{table}"):
            table_lines = [line]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith(r"\end{table}"):
                table_lines.append(lines[i].strip())
                i += 1
            if i < len(lines):
                table_lines.append(lines[i].strip())
                i += 1
            _insert_parsed_latex_table(doc, table_lines)
            continue

        # Code blocks / ASCII Diagrams
        if line.startswith("```"):
            if in_code_block:
                in_code_block = False
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after = Pt(6)
                p.paragraph_format.left_indent = Cm(0.8)
                run = p.add_run("\n".join(code_lines))
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Skip horizontal dividers
        if line.strip() in ("---", "***"):
            i += 1
            continue

        # Document Title (# Algorithmic...)
        if line.startswith("# "):
            title_text = line[2:].strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(12)
            run = p.add_run(title_text)
            run.bold = True
            run.font.size = Pt(14)
            i += 1
            continue

        # Heading 1 (## 1. Introduction)
        if line.startswith("## "):
            heading_text = line[3:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(heading_text)
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            continue

        # Heading 2 (### 2.1 The Evolution...)
        if line.startswith("### "):
            subheading_text = line[4:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(3)
            run = p.add_run(subheading_text)
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            continue

        # Heading 3 (#### 4.2.1 Banded...)
        if line.startswith("#### "):
            subsub_text = line[5:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(2)
            run = p.add_run(subsub_text)
            run.bold = True
            run.italic = True
            run.font.size = Pt(12)
            i += 1
            continue

        # UDC & Metadata
        if line.startswith("**UDC:**") or line.startswith("**DOI:**"):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.space_before = Pt(0)
            _add_formatted_text(p, line)
            i += 1
            continue

        # Author lines at top
        if line.startswith("**Askar Nurym**") or line.startswith("**Tamara Zhukabayeva**"):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(1)
            run = p.add_run(line.replace("**", ""))
            run.bold = True
            run.font.size = Pt(12)
            i += 1
            # Add subsequent affiliation line if present
            if i < len(lines) and lines[i].strip() and not lines[i].startswith("**"):
                affil_p = doc.add_paragraph()
                affil_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                affil_p.paragraph_format.space_before = Pt(0)
                affil_p.paragraph_format.space_after = Pt(4)
                affil_run = affil_p.add_run(lines[i].strip())
                affil_run.font.size = Pt(10.5)
                affil_run.italic = True
                i += 1
            # Add email line if present
            if i < len(lines) and "Email:" in lines[i]:
                email_p = doc.add_paragraph()
                email_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                email_p.paragraph_format.space_before = Pt(0)
                email_p.paragraph_format.space_after = Pt(6)
                email_run = email_p.add_run(lines[i].strip())
                email_run.font.size = Pt(10)
                i += 1
            continue

        # Abstract and Keywords
        if line.startswith("**Keywords:**"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(10)
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.right_indent = Cm(0.8)
            _add_formatted_text(p, line, font_size=Pt(11))
            i += 1
            continue

        # Bullet lists
        if line.strip().startswith("* ") or line.strip().startswith("- "):
            bullet_text = line.strip()[2:].strip()
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.0
            _add_formatted_text(p, bullet_text)
            i += 1
            continue

        # Numbered lists / References
        num_match = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if num_match and ("References" in lines[max(0, i - 40) : i] or i > 240):
            num = num_match.group(1)
            ref_body = num_match.group(2)
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8)
            p.paragraph_format.first_line_indent = Cm(-0.8)
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            num_run = p.add_run(f"{num}. ")
            num_run.font.size = Pt(11)
            num_run.bold = True
            _add_formatted_text(p, ref_body, font_size=Pt(11))
            i += 1
            continue

        # Math display lines ($$...$$)
        if line.startswith("$$") and line.endswith("$$") and len(line) > 4:
            math_text = line[2:-2].strip()
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(math_text)
            run.font.name = "Cambria Math"
            run.font.size = Pt(11)
            run.italic = True
            i += 1
            continue

        # Normal text paragraph
        if line.strip():
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            _add_formatted_text(p, line.strip())

        i += 1

    doc.save(docx_path)
    print(f"Successfully compiled manuscript to {docx_path}")
    print(f"File size: {docx_path.stat().st_size:,} bytes")


def _add_formatted_text(p, text: str, font_size=None):
    """Parse inline markdown formatting (bold, italic, code) into runs."""
    if font_size is None:
        font_size = Pt(12)
    tokens = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\$[^$]+\$)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = p.add_run(token[2:-2])
            run.bold = True
            run.font.name = "Times New Roman"
            run.font.size = font_size
        elif token.startswith("*") and token.endswith("*"):
            run = p.add_run(token[1:-1])
            run.italic = True
            run.font.name = "Times New Roman"
            run.font.size = font_size
        elif token.startswith("`") and token.endswith("`"):
            run = p.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(10.5)
        elif token.startswith("$") and token.endswith("$"):
            run = p.add_run(token[1:-1])
            run.font.name = "Cambria Math"
            run.font.size = font_size
            run.italic = True
        else:
            run = p.add_run(token)
            run.font.name = "Times New Roman"
            run.font.size = font_size


def _insert_parsed_latex_table(doc, table_lines: list[str]):
    """Insert a professional formatted Word table parsed from LaTeX lines."""
    caption = "Table"
    for line_item in table_lines:
        if r"\caption{" in line_item:
            caption = line_item.split(r"\caption{")[1].split("}")[0]

    caption_p = doc.add_paragraph()
    caption_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    caption_p.paragraph_format.space_before = Pt(8)
    caption_p.paragraph_format.space_after = Pt(3)
    caption_run = caption_p.add_run(caption)
    caption_run.bold = True
    caption_run.font.size = Pt(11)

    # Extract tabular rows
    rows = []
    in_tabular = False
    for line_item in table_lines:
        if r"\begin{tabular}" in line_item:
            in_tabular = True
            continue
        if r"\end{tabular}" in line_item:
            in_tabular = False
            continue
        if in_tabular and r"\\" in line_item:
            cleaned = line_item.replace(r"\\", "").strip()
            ignored = (r"\toprule", r"\midrule", r"\bottomrule")
            if cleaned and not any(cleaned.startswith(ign) for ign in ignored):
                cells = [
                    c.strip()
                    .replace(r"\%", "%")
                    .replace(r"\_", "_")
                    .replace(r"\times", "x")
                    .replace("$", "")
                    for c in cleaned.split("&")
                ]
                rows.append(cells)

    if not rows:
        return

    num_rows = len(rows)
    num_cols = max(len(r) for r in rows)

    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for r_idx, row in enumerate(rows):
        for c_idx, cell_value in enumerate(row):
            if c_idx < num_cols:
                cell = table.cell(r_idx, c_idx)
                cell.text = cell_value
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 0 else WD_ALIGN_PARAGRAPH.RIGHT
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.line_spacing = 1.0
                run = p.runs[0] if p.runs else p.add_run(cell_value)
                run.font.name = "Times New Roman"
                run.font.size = Pt(10.5)

                if r_idx == 0:
                    run.bold = True
                    set_cell_borders(cell, top="single", bottom="single")
                elif r_idx == num_rows - 1:
                    set_cell_borders(cell, bottom="single")
                else:
                    set_cell_borders(cell)

    after_p = doc.add_paragraph()
    after_p.paragraph_format.space_before = Pt(2)
    after_p.paragraph_format.space_after = Pt(6)


if __name__ == "__main__":
    compile_manuscript()
