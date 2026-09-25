from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def sha256_file(path: Path | str) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(root: Path | str) -> str | None:
    injected = os.getenv("EXPERIAN_GIT_COMMIT")
    if injected:
        return injected.strip() or None

    root = Path(root)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def git_is_dirty(root: Path | str) -> bool | None:
    injected = os.getenv("EXPERIAN_GIT_DIRTY")
    if injected is not None:
        value = injected.strip().lower()
        if value in {"1", "true", "yes"}:
            return True
        if value in {"0", "false", "no"}:
            return False
        return None

    root = Path(root)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None
    return bool(result.stdout.strip())
