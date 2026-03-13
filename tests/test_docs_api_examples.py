import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _load_checker_module() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "check_docs_api_examples.py"
    spec = importlib.util.spec_from_file_location(
        "check_docs_api_examples",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load check_docs_api_examples module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analyze_python_block_detects_legacy_arguments_and_fields() -> None:
    """Detect deprecated args and result fields in python code blocks."""
    checker = _load_checker_module()
    source = """
result = run_backtest(
    strategy_class=MyStrategy,
    cash=100_000,
    commission=0.0003,
)
opt = run_optimization(strategy=MyStrategy, cash=1000, commission=0.0)
print(result.final_value, result.total_return)
"""
    violations = checker._analyze_python_block(Path("sample.md"), 1, source)
    labels = [item[2] for item in violations]
    assert labels.count("legacy_api_argument") == 5
    assert "legacy_result_field_final_value" in labels
    assert "legacy_result_field_total_return" in labels


def test_resolve_scan_files_keeps_only_markdown_in_docs(tmp_path: Path) -> None:
    """Keep only markdown files located under the docs root."""
    checker = _load_checker_module()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    valid_md = docs_dir / "a.md"
    valid_md.write_text("# ok", encoding="utf-8")
    invalid_txt = docs_dir / "b.txt"
    invalid_txt.write_text("x", encoding="utf-8")
    outside_md = tmp_path / "outside.md"
    outside_md.write_text("# outside", encoding="utf-8")

    resolved = checker._resolve_scan_files(
        docs_dir,
        [
            str(valid_md),
            str(invalid_txt),
            str(outside_md),
            str(docs_dir / "missing.md"),
        ],
    )
    assert resolved == [valid_md.resolve()]


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
    """Return only changed markdown files in docs between two revisions."""
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
