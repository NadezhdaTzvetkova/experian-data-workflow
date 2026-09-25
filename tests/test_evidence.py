from pathlib import Path

from experian_workflow import evidence


def test_injected_git_commit_overrides_repository_lookup(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERIAN_GIT_COMMIT", "abc123")

    assert evidence.git_commit(tmp_path) == "abc123"


def test_injected_git_dirty_false(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERIAN_GIT_DIRTY", "false")

    assert evidence.git_is_dirty(tmp_path) is False


def test_injected_git_dirty_true(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERIAN_GIT_DIRTY", "true")

    assert evidence.git_is_dirty(tmp_path) is True


def test_invalid_injected_git_dirty_returns_unknown(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EXPERIAN_GIT_DIRTY", "unexpected")

    assert evidence.git_is_dirty(tmp_path) is None


def test_missing_git_executable_returns_unknown(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("EXPERIAN_GIT_COMMIT", raising=False)
    monkeypatch.delenv("EXPERIAN_GIT_DIRTY", raising=False)

    def raise_oserror(*args, **kwargs):
        raise OSError("git executable not available")

    monkeypatch.setattr(evidence.subprocess, "run", raise_oserror)

    assert evidence.git_commit(tmp_path) is None
    assert evidence.git_is_dirty(tmp_path) is None