"""Inventory full local PDFs and BibTeX links; matching is advisory, not evidence review.

uv run --no-project --with pymupdf python scripts/audit_literature_inventory.py
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import unicodedata
from pathlib import Path


def normal(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in text if c.isalnum())


def entries(text: str) -> list[dict]:
    """Read brace-valued fields, preserving nested BibTeX title/author accents."""
    starts = list(re.finditer(r"@(\w+)\s*\{\s*([^,]+),", text))
    result = []
    for index, start in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[start.end() : end]
        item = {"key": start[2].strip(), "type": start[1]}
        for field in re.finditer(r"^\s*(\w+)\s*=\s*\{", body, re.MULTILINE):
            pos, depth = field.end(), 1
            cursor = pos
            while cursor < len(body) and depth:
                char = body[cursor]
                if char == "{" and (cursor == 0 or body[cursor - 1] != "\\"):
                    depth += 1
                elif char == "}" and (cursor == 0 or body[cursor - 1] != "\\"):
                    depth -= 1
                cursor += 1
            item[field[1].lower()] = body[pos : cursor - 1]
        result.append(item)
    return result


def main() -> None:
    import pymupdf

    p = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    p.add_argument("--base", type=Path, default=Path.home() / "Desktop/Thesis/Article base")
    p.add_argument(
        "--output", type=Path, default=root / "reports/literature_audit_20261106/inventory.json"
    )
    args = p.parse_args()
    sources = sorted(set(args.base.rglob("*.pdf")) | set((root / "literature/pdf").glob("*.pdf")))
    inventory = []
    for path in sources:
        data = path.read_bytes()
        item = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
        try:
            with pymupdf.open(path) as doc:
                item.update(
                    {"pages": len(doc), "metadata": doc.metadata, "encrypted": doc.is_encrypted}
                )
                item["first_page"] = doc[0].get_text() if len(doc) else ""
                item["parse_ok"] = len(doc) > 0 and not doc.is_encrypted
        except Exception as err:
            item.update({"parse_ok": False, "error": f"{type(err).__name__}: {err}"})
        inventory.append(item)
    library = entries((root / "docs/paper/references.bib").read_text(encoding="utf-8"))
    for item in library:
        title = normal(item.get("title", ""))
        matches = [pdf for pdf in inventory if title and title in normal(pdf.get("first_page", ""))]
        note = re.search(r"Local PDF:\s*(.*?\.pdf)", item.get("note", ""))
        explicit = None
        if note:
            relative = note[1]
            explicit = (
                (args.base / relative.removeprefix("Thesis/Article base/"))
                if relative.startswith("Thesis/")
                else root / relative
            )
        item["explicit_pdf_exists"] = explicit.is_file() if explicit else None
        item["title_matched_pdfs"] = [pdf["path"] for pdf in matches]
        item["review_status"] = "requires_full_text_and_metadata_review"
        item["age_in_2026"] = 2026 - int(item["year"]) if item.get("year", "").isdigit() else None
    by_hash = {}
    for pdf in inventory:
        by_hash.setdefault(pdf["sha256"], []).append(pdf["path"])
    report = {
        "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
        "scope": str(args.base.parent / ".agents/teamwork/orchestrator_3/PROJECT.md"),
        "limitations": [
            "Title matches establish file identity candidates, not support for a scientific claim.",
            "Indexing, retractions, page evidence and legal availability require separate verification.",
            "All base/archive PDFs are inventoried; this does not select them for the article.",
        ],
        "bib_entries": library,
        "pdf_inventory": inventory,
        "duplicate_files": [paths for paths in by_hash.values() if len(paths) > 1],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Inventoried {len(inventory)} PDFs, {len(library)} BibTeX entries")
    print(f"Unreadable PDFs: {sum(not x['parse_ok'] for x in inventory)}")
    print(
        "Entries without title-matched PDF:",
        ", ".join(x["key"] for x in library if not x["title_matched_pdfs"]),
    )


if __name__ == "__main__":
    main()
