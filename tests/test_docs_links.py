import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_checker_module() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "check_docs_links.py"
    spec = importlib.util.spec_from_file_location("check_docs_links", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load check_docs_links module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classify_target_detects_local_path_styles() -> None:
    """Detect local-path style markdown targets as violations."""
    checker = _load_checker_module()
    assert checker._classify_target("file:///tmp/a.md") == "file_scheme"
    assert checker._classify_target("C:\\a\\b.md") == "windows_drive_path"
    assert checker._classify_target("/Users/albert/a.md") == "unix_local_absolute_path"
    assert checker._classify_target("https://example.com") is None


def test_scan_markdown_files_reports_local_links(tmp_path: Path) -> None:
    """Report violations for file:// and absolute local links in docs markdown."""
    checker = _load_checker_module()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    md_file = docs_dir / "x.md"
    md_file.write_text(
        "\n".join(
            [
                "[ok](https://example.com)",
                "[bad](file:///tmp/a.md)",
                "[bad2](/Users/albert/b.md)",
            ]
        ),
        encoding="utf-8",
    )
    violations = checker._scan_markdown_files(docs_dir)
    labels = [item[2] for item in violations]
    assert "file_scheme" in labels
    assert "unix_local_absolute_path" in labels


def test_resolve_project_path_is_cwd_independent() -> None:
    """Resolve relative paths against repository root, not current cwd."""
    checker = _load_checker_module()
    checker_file = checker.__file__
    assert checker_file is not None
    expected = (Path(checker_file).resolve().parents[1] / "docs").resolve()
    assert checker._resolve_project_path("docs") == expected


def test_changed_files_between_revs_returns_docs_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return only changed docs markdown files between revisions."""
    checker = _load_checker_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    docs_dir = repo / "docs"
    docs_dir.mkdir()
    tracked = docs_dir / "tracked.md"
    tracked.write_text("# v1\n", encoding="utf-8")
    unrelated = repo / "README.md"
    unrelated.write_text("# readme\n", encoding="utf-8")

    subprocess.run(
        ["git", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "tester"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "tester@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "add", "."],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    base_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    tracked.write_text("# v2\n", encoding="utf-8")
    unrelated.write_text("# changed\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "."],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "update"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    head_rev = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    old_cwd = Path.cwd()
    try:
        import os

        monkeypatch.setattr(checker, "PROJECT_ROOT", repo.resolve())
        os.chdir(repo)
        changed = checker._changed_files_between_revs(
            docs_dir.resolve(),
            base_rev,
            head_rev,
        )
    finally:
        os.chdir(old_cwd)

    assert changed == [tracked.resolve()]


def test_changed_files_between_revs_falls_back_when_git_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback to full scan when git command execution fails."""
    checker = _load_checker_module()

    def _fake_run_git_command(_args: list[str]) -> None:
        return None

    monkeypatch.setattr(checker, "_run_git_command", _fake_run_git_command)
    result = checker._changed_files_between_revs(Path("/tmp/docs"), "a", "b")
    assert result is None
