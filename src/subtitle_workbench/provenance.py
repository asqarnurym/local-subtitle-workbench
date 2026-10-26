"""Provenance audit metadata and cryptographic hashing."""

import hashlib
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path | str) -> str:
    """Compute SHA-256 digest of a file in 64 KB blocks."""
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def code_provenance() -> dict:
    """Fingerprint the installed code; attach revision only for this package's repository."""
    package = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for source in sorted(package.glob("*.py")):
        digest.update(source.name.encode("utf-8") + b"\0" + source.read_bytes())
    result = {"source_sha256": digest.hexdigest(), "git_revision": None, "git_worktree_dirty": None}
    repository = package.parent.parent
    if shutil.which("git") is None:
        return result
    try:

        def git(*arguments: str) -> str:
            completed = subprocess.run(
                ["git", "-C", str(repository), *arguments],
                capture_output=True,
                text=True,
                check=True,
                timeout=2,
            )
            return completed.stdout.strip()

        if Path(git("rev-parse", "--show-toplevel")).resolve() == repository:
            result["git_revision"] = git("rev-parse", "HEAD")
            result["git_worktree_dirty"] = bool(git("status", "--porcelain"))
    except (OSError, subprocess.SubprocessError):
        pass
    return result


__all__ = [
    "code_provenance",
    "sha256",
]
