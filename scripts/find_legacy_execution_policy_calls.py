from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TARGET_CALLS = {"run_backtest", "run_warm_start"}
IGNORE_PARTS = {".venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache"}


@dataclass(frozen=True)
class LegacyCallSite:
    """One legacy execution-policy callsite in source code."""

    file_path: Path
    line: int
    func_name: str
    has_execution_mode: bool
    has_timer_execution_policy: bool
    has_fill_policy: bool
    has_compat_gate: bool

    @property
    def is_test_scope(self) -> bool:
        """Return whether the callsite comes from tests directory."""
        normalized = self.file_path.as_posix().lower()
        return normalized.startswith("tests/")

    @property
    def suggested_action(self) -> str:
        """Return suggested migration action for this callsite."""
        if not self.is_test_scope:
            return "remove_required"
        return "keep_removal_test"


def _iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(part in IGNORE_PARTS for part in path.parts):
            continue
        yield path


def _call_name(node: ast.Call) -> str | None:
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _extract_kwarg_flags(node: ast.Call) -> tuple[bool, bool, bool, bool]:
    names = {kw.arg for kw in node.keywords if kw.arg is not None}
    return (
        "execution_mode" in names,
        "timer_execution_policy" in names,
        "fill_policy" in names,
        "legacy_execution_policy_compat" in names,
    )


def collect_legacy_calls(root: Path) -> list[LegacyCallSite]:
    """Collect callsites that still pass legacy execution policy kwargs."""
    findings: list[LegacyCallSite] = []
    for file_path in _iter_python_files(root):
        source = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = _call_name(node)
            if func_name not in TARGET_CALLS:
                continue
            has_execution_mode, has_timer, has_fill_policy, has_compat_gate = (
                _extract_kwarg_flags(node)
            )
            if not has_execution_mode and not has_timer and not has_compat_gate:
                continue
            findings.append(
                LegacyCallSite(
                    file_path=file_path,
                    line=node.lineno,
                    func_name=func_name,
                    has_execution_mode=has_execution_mode,
                    has_timer_execution_policy=has_timer,
                    has_fill_policy=has_fill_policy,
                    has_compat_gate=has_compat_gate,
                )
            )
    return findings


def format_report(root: Path, findings: list[LegacyCallSite]) -> str:
    """Format findings as a markdown report."""
    test_scope_findings = [finding for finding in findings if finding.is_test_scope]
    non_test_scope_findings = [
        finding for finding in findings if not finding.is_test_scope
    ]
    lines = [
        "# Legacy Execution Policy Callsite Report",
        "",
        f"- Scan root: `{root}`",
        f"- Total legacy callsites: **{len(findings)}**",
        f"- Legacy callsites in tests: **{len(test_scope_findings)}**",
        f"- Legacy callsites outside tests: **{len(non_test_scope_findings)}**",
        "",
        (
            "| Scope | File | Line | API | execution_mode | timer_execution_policy | "
            "fill_policy | compat_gate | suggested_action |"
        ),
        "| :--- | :--- | ---: | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]
    for finding in sorted(findings, key=lambda x: (str(x.file_path), x.line)):
        relative = finding.file_path.as_posix()
        scope = "test" if finding.is_test_scope else "non_test"
        lines.append(
            "| "
            + " | ".join(
                [
                    scope,
                    relative,
                    str(finding.line),
                    finding.func_name,
                    "yes" if finding.has_execution_mode else "no",
                    "yes" if finding.has_timer_execution_policy else "no",
                    "yes" if finding.has_fill_policy else "no",
                    "yes" if finding.has_compat_gate else "no",
                    finding.suggested_action,
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    """CLI entrypoint for legacy execution-policy callsite scanning."""
    parser = argparse.ArgumentParser(
        description="Find legacy execution policy callsites."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Project root to scan.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("tests/golden/LEGACY_EXECUTION_CALLS.md"),
        help="Markdown report output path.",
    )
    args = parser.parse_args()
    findings = collect_legacy_calls(args.root)
    report = format_report(args.root, findings)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote report to {args.out}")


if __name__ == "__main__":
    main()
