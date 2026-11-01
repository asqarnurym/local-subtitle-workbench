"""Check final E1 graphics against an already verified, unchanged numerical report.

Layout edits do not require repeating the full sign-permutation enumeration.
The previous numerical verdict is pinned by SHA-256; its inputs are rechecked.
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

import PIL
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.replay_frozen_metrics import write_json  # noqa: E402
from scripts.verify_frozen_evidence import digest, local_path, read_json, require  # noqa: E402
from subtitle_workbench.provenance import code_provenance  # noqa: E402


def check(work: Path, expected_numerical_sha256: str) -> dict:
    numeric_path = work / "independent_check.json"
    require(
        digest(numeric_path) == expected_numerical_sha256, "Numerical verification hash mismatch"
    )
    numerical = read_json(numeric_path.relative_to(ROOT).as_posix())
    analysis_path, manifest_path = work / "analysis.json", work / "figure_manifest.json"
    analysis = read_json(analysis_path.relative_to(ROOT).as_posix())
    require(
        numerical["status"] == "VERIFIED" and analysis["status"] == "COMPLETE",
        "Unverified numerical data",
    )
    require(
        numerical["analysis_sha256"] == digest(analysis_path),
        "Analysis changed since numerical verification",
    )
    for relative, sha in analysis["protected_files"].items():
        require(digest(local_path(relative)) == sha, f"Protected input changed: {relative}")
    for corpus in analysis["corpora"].values():
        require(
            digest(local_path(corpus["ledger"]["path"])) == corpus["ledger"]["sha256"],
            "Boundary ledger changed",
        )
    manifest = read_json(manifest_path.relative_to(ROOT).as_posix())
    require(manifest["analysis_sha256"] == digest(analysis_path), "Figures use different data")
    require(
        manifest["renderer_sha256"] == digest(ROOT / "scripts/render_error_analysis.py"),
        "Renderer fingerprint differs",
    )
    require(
        len(manifest["files"]) == 24 and len(manifest["tables"]) == 2,
        "Incomplete final figures/tables",
    )
    sizes = {}
    for relative, item in manifest["files"].items():
        path = local_path(relative)
        require(digest(path) == item["sha256"], f"Figure fingerprint differs: {relative}")
        if path.suffix == ".png":
            with Image.open(path) as im:
                im.verify()
            with Image.open(path) as im:
                require(
                    min(im.info.get("dpi", (0, 0))) >= 299.9 and min(im.size) >= 1000,
                    "Insufficient PNG resolution",
                )
                sizes[relative] = {"pixels": list(im.size), "dpi": list(im.info["dpi"])}
        else:
            require(
                path.suffix == ".pdf" and path.read_bytes().startswith(b"%PDF-"),
                "Invalid PDF export",
            )
    for relative, sha in manifest["tables"].items():
        path = local_path(relative)
        require(digest(path) == sha, "Speaker table changed")
        corpus = path.stem.removeprefix("speaker_tests_")
        lines = [
            line
            for line in path.read_text().splitlines()
            if " & " in line and not line.startswith("Comparison")
        ]
        require(len(lines) == 7, "Speaker table incomplete")
        for line, item in zip(
            lines, analysis["corpora"][corpus]["speaker_comparisons"].values(), strict=True
        ):
            cells = [v.strip() for v in line.removesuffix(r"\\").split("&")]
            require(
                int(cells[1]) == item["n_pairs"] and int(cells[2]) == item["n_speakers_improved"],
                "Speaker table denominator changed",
            )
            require(
                float(cells[3]) == float(f"{item['p_value_holm']:.6g}"), "Table p-value changed"
            )
    return {
        "schema_version": 1,
        "status": "VERIFIED",
        "scope": "Final figure/table integrity and resolution; prior complete numerical verification reused only after its SHA-256, analysis, ledgers and protected inputs were checked unchanged.",
        "numerical_verification_sha256": expected_numerical_sha256,
        "analysis_sha256": digest(analysis_path),
        "figure_manifest_sha256": digest(manifest_path),
        "checker_sha256": digest(Path(__file__).resolve()),
        "python": platform.python_version(),
        "pillow": PIL.__version__,
        "figure_files_verified": len(manifest["files"]),
        "table_files_verified": len(manifest["tables"]),
        "png_checks": sizes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-dir", required=True)
    parser.add_argument("--numeric-sha256", required=True)
    args = parser.parse_args()
    work = local_path(args.analysis_dir)
    require(not (work / "figure_check.json").exists(), "Final figure verdict already exists")
    code = code_provenance()
    require(code["git_worktree_dirty"] is False, "Commit figure verification code first")
    result = check(work, args.numeric_sha256)
    result["code_start"], result["code_end"] = code, code_provenance()
    require(result["code_start"] == result["code_end"], "Worktree changed during verification")
    write_json(work / "figure_check.json", result)
    print("[+] Final figure verification passed; prior numerical verification unchanged")


if __name__ == "__main__":
    main()
