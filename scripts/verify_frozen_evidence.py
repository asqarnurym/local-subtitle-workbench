"""Audit the existing frozen runs without loading or running speech models.

Requires the laptop's local corpora and per-clip outputs. It does not rerun metrics
or attest historical reference integrity: reference hashes are an audit-time snapshot.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import re
import subprocess
import sys
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_paper_tables import (  # noqa: E402
    generate_alignment_accuracy_table,
    generate_quality_estimation_table,
    generate_statistical_significance_table,
)

RUNS = {
    "timit": "bench-frozen-20261029",
    "buckeye": "bench-frozen-20261029c",
    "brqe_train_run": "9dc8018de6d9debef7d6765b40630903eaf2cbdd",
}
# Observed on the source-of-truth laptop on 2026-11-01. The run fingerprint
# hashes raw bytes, so these per-file newline styles are needed to reconstruct it
# from Git's normalized blobs. This does not modify any checkout or source file.
CRLF_SOURCES = {
    "__main__.py",
    "anchoring.py",
    "api.py",
    "asr.py",
    "buckeye.py",
    "chunker.py",
    "cli.py",
    "corpora.py",
    "demo.py",
    "dtw.py",
    "metrics.py",
    "mfa_wrapper.py",
    "models.py",
    "phone_sets.py",
    "pipeline.py",
    "text_norm.py",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def local_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), f"Path outside repository: {relative}")
    return path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_digest(relative: str, expected: str) -> str:
    actual = digest(local_path(relative))
    require(actual == expected, f"SHA-256 mismatch: {relative}")
    return actual


def read_json(relative: str):
    return json.loads(local_path(relative).read_text(encoding="utf-8"))


def verify_reference_snapshot(current: dict, baseline: dict) -> None:
    actual = current["reference_snapshot"]["files"]
    expected = baseline["reference_snapshot"]["files"]
    changed = sorted(key for key in actual.keys() & expected.keys() if actual[key] != expected[key])
    added, missing = (
        sorted(actual.keys() - expected.keys()),
        sorted(expected.keys() - actual.keys()),
    )
    require(
        not changed and not added and not missing,
        f"Reference snapshot mismatch: changed={changed[:5]}, added={added[:5]}, missing={missing[:5]}",
    )


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def source_fingerprint(revision: str) -> dict:
    prefix = "src/subtitle_workbench/"
    paths = sorted(
        p
        for p in git("ls-tree", "-r", "--name-only", revision, prefix).decode().splitlines()
        if p.endswith(".py") and "/" not in p[len(prefix) :]
    )
    require(bool(paths), f"No package sources at {revision}")
    raw, normalized = hashlib.sha256(), hashlib.sha256()
    styles = {}
    for relative in paths:
        name = Path(relative).name
        blob = git("show", f"{revision}:{relative}").replace(b"\r\n", b"\n")
        normalized.update(name.encode() + b"\0" + blob)
        styles[name] = "CRLF" if name in CRLF_SOURCES else "LF"
        checkout = blob.replace(b"\n", b"\r\n") if name in CRLF_SOURCES else blob
        raw.update(name.encode() + b"\0" + checkout)
    return {
        "reconstructed_run_sha256": raw.hexdigest(),
        "normalized_lf_sha256": normalized.hexdigest(),
        "reconstruction_newlines": styles,
    }


def audit() -> dict:
    checked_at = datetime.datetime.now(datetime.UTC)
    audit_date = (
        checked_at.astimezone(datetime.timezone(datetime.timedelta(hours=5))).date().isoformat()
    )
    inventory, snapshots, runs = {}, {}, {}

    def record(relative: str) -> None:
        path = local_path(relative)
        inventory[relative] = {"sha256": digest(path), "bytes": path.stat().st_size}

    split_path = "reports/buckeye_split_20260401.json"
    split = read_json(split_path)
    train, test = set(split["train_speakers"]), set(split["test_speakers"])
    require(len(train) == len(test) == 20 and not train & test, "Invalid speaker split")
    record(split_path)
    wav_index = {}
    for corpus in ("timit", "buckeye"):
        base = local_path(f"data/corpora/{corpus}")
        index = {}
        for path in sorted(base.rglob("*")):
            if path.suffix.lower() != ".wav":
                continue
            uid = (
                f"{path.parent.name.lower()}_{path.stem.lower()}"
                if corpus == "timit"
                else path.stem
            )
            require(uid not in index, f"Duplicate audio ID: {uid}")
            index[uid] = path
        wav_index[corpus] = index

    for name, tag in RUNS.items():
        base = f"reports/{name}"
        manifest, result = (
            read_json(f"{base}/manifest.json"),
            read_json(f"{base}/benchmark_results.json"),
        )
        record(f"{base}/manifest.json")
        expected_revision = git("rev-parse", f"{tag}^{{commit}}").decode().strip()
        code = manifest["code"]
        require(code["git_revision"] == expected_revision, f"Revision mismatch: {name}")
        require(code["git_worktree_dirty"] is False, f"Dirty execution tree: {name}")
        source = source_fingerprint(expected_revision)
        require(
            source["reconstructed_run_sha256"] == code["source_sha256"], f"Source mismatch: {name}"
        )
        for filename, metadata in manifest["outputs"].items():
            require(filename == Path(filename).name, f"Invalid output filename: {filename}")
            verify_digest(f"{base}/{filename}", metadata["sha256"])
            record(f"{base}/{filename}")
        require(manifest["config"] == result["config"], f"Config mismatch: {name}")
        require(manifest["timestamp"] == result["timestamp"], f"Timestamp mismatch: {name}")
        for key in (
            "corpus",
            "reference_type",
            "data_provenance",
            "offline_synthetic",
            "n_utterances",
            "n_speakers",
        ):
            require(manifest["inputs"][key] == result[key], f"Input mismatch: {name}/{key}")
        require(
            result["data_provenance"] == "MODEL_EXECUTION" and result["reference_type"] == "gold",
            f"Unverified results: {name}",
        )
        require(result["offline_synthetic"] is False, f"Simulated run: {name}")
        require(result["config"]["ci_unit"] == "speaker", f"Unexpected CI unit: {name}")
        require(
            result["config"]["asr"]["device"] == "cuda"
            and manifest["hardware"]["whisper_cuda_available"] is True,
            f"CUDA record missing: {name}",
        )
        ids = set(manifest["inputs"]["audio_files"])
        require(len(ids) == result["n_utterances"], f"Audio count mismatch: {name}")
        for uid, sha in manifest["inputs"]["audio_files"].items():
            audio = wav_index[result["corpus"]][uid]
            verify_digest(audio.relative_to(ROOT).as_posix(), sha)
            suffixes = (".wrd", ".phn") if result["corpus"] == "timit" else (".TextGrid",)
            for suffix in suffixes:
                ref = next(
                    p
                    for ext in dict.fromkeys((suffix, suffix.lower(), suffix.upper()))
                    if (p := audio.with_suffix(ext)).is_file()
                )
                snapshots[ref.relative_to(ROOT).as_posix()] = digest(ref)
        rows = read_json(f"{base}/benchmark_utterances.json")
        modes = result["config"]["modes"]
        require(set(modes) == set(result["modes"]), f"Mode mismatch: {name}")
        pairs = {(row["mode"], row["utterance"]) for row in rows}
        require(
            len(rows) == len(pairs) == len(ids) * len(modes), f"Row count or duplicate pair: {name}"
        )
        require(
            pairs == {(mode, uid) for mode in modes for uid in ids}, f"Row IDs mismatch: {name}"
        )
        require(
            len({r["speaker"] for r in rows}) == result["n_speakers"],
            f"Speaker count mismatch: {name}",
        )
        predictions = read_json(f"{base}/benchmark_predictions.json")["modes"]
        require(set(predictions) == set(modes), f"Prediction modes mismatch: {name}")
        failures = {}
        for mode in modes:
            require(set(predictions[mode]) == ids, f"Prediction IDs mismatch: {name}/{mode}")
            failed = [r for r in rows if r["mode"] == mode and r["status"] == "failed"]
            require(
                len(failed) == result["modes"][mode]["n_utterances_failed"],
                f"Failure count mismatch: {name}/{mode}",
            )
            failures[mode] = [{"utterance": r["utterance"], "error": r["error"]} for r in failed]
        sample_record = result["config"].get("sample")
        if sample_record:
            verify_digest(sample_record["path"], sample_record["sha256"])
            record(sample_record["path"])
            sample = read_json(sample_record["path"])
            sampled = sample["utterance_ids"]
            require(
                len(sampled) == len(set(sampled)) == sample_record["n_utterances"],
                f"Invalid sample: {name}",
            )
            excluded = result["config"].get("excluded_corpus_defects", {})
            require(
                not ids & set(excluded) and set(sampled) == ids | set(excluded),
                f"Sample selection mismatch: {name}",
            )
            group = train if name == "brqe_train_run" else test
            require({r["speaker"] for r in rows} == group, f"Wrong speaker group: {name}")
            for uid, reason in excluded.items():
                require(reason == "empty audio", f"Unexpected exclusion: {uid}")
                with wave.open(str(wav_index[result["corpus"]][uid]), "rb") as wav:
                    require(wav.getnframes() == 0, f"Nonempty excluded audio: {uid}")
        if name != "brqe_train_run":
            refiner = result["config"]["refiners"]
            for filename, key in (
                ("brqe.pt", "brqe_weights_sha256"),
                ("const_offsets.json", "const_offsets_sha256"),
            ):
                relative = f"{refiner['dir']}/{filename}"
                verify_digest(relative, refiner[key])
                record(relative)
            meta_path = f"{refiner['dir']}/brqe.json"
            meta = read_json(meta_path)
            record(meta_path)
            require(
                meta["weights_sha256"] == refiner["brqe_weights_sha256"],
                f"Model metadata mismatch: {name}",
            )
            require(
                meta["config"] == refiner["brqe_config"]
                and meta["trained_on"] == refiner["trained_on"],
                f"Training metadata mismatch: {name}",
            )
            for key in ("sample", "split"):
                item = refiner["trained_on"][key]
                verify_digest(item["path"], item["sha256"])
                record(item["path"])
            generators = {
                "table_alignment_accuracy.tex": generate_alignment_accuracy_table,
                "table_statistical_significance.tex": generate_statistical_significance_table,
                "table_quality_estimation.tex": generate_quality_estimation_table,
            }
            for filename, generator in generators.items():
                relative = f"{base}/tables/{filename}"
                require(
                    local_path(relative).read_text(encoding="utf-8") == generator(result),
                    f"Stale table: {relative}",
                )
                record(relative)
        runs[name] = {
            "revision_or_tag": tag,
            "git_revision": expected_revision,
            "source_fingerprint": source,
            "n_utterances": len(ids),
            "n_speakers": result["n_speakers"],
            "audio_hashes_verified": len(ids),
            "rows_verified": len(rows),
            "failures": failures,
            "excluded_corpus_defects": result["config"].get("excluded_corpus_defects", {}),
        }
    cv = read_json("reports/brqe_cv_20260401.json")
    held_out = [s for fold in cv["folds"] for s in fold["held_out"]]
    require(Counter(held_out) == Counter(train), "CV folds do not partition train speakers")
    final = read_json("reports/brqe_final_20260401.json")
    model = read_json("models/brqe/brqe.json")
    require(
        final["weights_sha256"] == model["weights_sha256"],
        "Final report model mismatch",
    )
    require(cv["config"] == final["config"] == model["config"], "CV/final config mismatch")
    require(cv["input"] == final["input"] == model["trained_on"], "CV/final input mismatch")
    require(
        cv["code"]["source_sha256"]
        == final["code"]["source_sha256"]
        == runs["brqe_train_run"]["source_fingerprint"]["reconstructed_run_sha256"],
        "CV/final package source mismatch",
    )
    for path in (
        "reports/brqe_cv_20260401.json",
        "reports/brqe_final_20260401.json",
        "docs/CLAIM_LEDGER.csv",
    ):
        record(path)
    with local_path("docs/CLAIM_LEDGER.csv").open(encoding="utf-8", newline="") as stream:
        claims = list(csv.DictReader(stream))
    require(len({c["claim_id"] for c in claims}) == len(claims), "Duplicate claim IDs")
    checked_claims = []
    for claim in claims:
        if claim["status"] != "MODEL_EXECUTION":
            continue
        require(
            None not in claim and all(v is not None for v in claim.values()), "Malformed claim row"
        )
        sources = re.findall(r"reports/[\w/.-]+\.json", claim["source_location"])
        require(bool(sources), f"Missing claim sources: {claim['claim_id']}")
        for relative in sources:
            require(local_path(relative).is_file(), f"Missing claim source: {relative}")
        checked_claims.append({"claim_id": claim["claim_id"], "sources": sources})
    return {
        "schema_version": 1,
        "audited_on": audit_date,
        "checked_at_utc": checked_at.isoformat(),
        "status": "PASS_WITH_LIMITATIONS",
        "scope": "Artifact integrity and consistency; no models, metric recomputation or new significance tests.",
        "runs": runs,
        "claims_with_resolved_sources": checked_claims,
        "files": dict(sorted(inventory.items())),
        "reference_snapshot": {
            "recorded_on": audit_date,
            "historical_integrity": "NOT_VERIFIABLE_FROM_ORIGINAL_MANIFESTS",
            "files": dict(sorted(snapshots.items())),
        },
        "limitations": [
            "Original manifests hash audio and outputs but not reference annotations; reference hashes are recorded only at audit time.",
            "Package source fingerprints omit scripts, lockfile and model-cache contents; Git revisions identify tracked files, not external model weights.",
            "Per-clip predictions, rows and training-run files remain local; this Git archive alone cannot recompute statistics.",
            "Final BRQE training report records a dirty worktree; exact historical uncommitted changes cannot be recovered from this report. Saved weights match both test runs.",
            "Training-data run records the revision at completion; the documented start revision was earlier (IMPROVEMENT_PLAN section 6.5).",
            "Claim checks resolve evidence paths; they do not independently reproduce every numeric claim or assess scientific validity of significance tests.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="reports/frozen_evidence_audit_20261101.json")
    parser.add_argument(
        "--output", help="Optional separate recheck report; the baseline is read-only"
    )
    args = parser.parse_args()
    baseline = read_json(args.baseline)
    report = audit()
    verify_reference_snapshot(report, baseline)
    if args.output is not None:
        path = local_path(args.output)
        require(path != local_path(args.baseline), "Refusing to overwrite the reference baseline")
        require(
            path.parent == ROOT / "reports" and path.suffix == ".json",
            "Audit output must be a JSON file directly under reports/",
        )
        if path.exists():
            existing = read_json(args.output)
            require(
                isinstance(existing, dict)
                and "reference_snapshot" in existing
                and "claims_with_resolved_sources" in existing,
                "Refusing to overwrite an existing file that is not an evidence audit",
            )
        path.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(
        f"PASS_WITH_LIMITATIONS: {len(report['runs'])} runs, {len(report['files'])} artifacts, "
        f"{len(report['reference_snapshot']['files'])} reference files match {args.baseline}"
    )


if __name__ == "__main__":
    main()
