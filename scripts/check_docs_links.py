import argparse
import re
import subprocess
import sys
from pathlib import Path

MARKDOWN_LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve_project_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def _run_git_command(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
    except OSError as exc:
        print(f"docs link check fallback: failed to run {' '.join(args)} ({exc})")
        return None


def _classify_target(target: str) -> str | None:
    lowered = target.lower()
    if lowered.startswith("file://"):
        return "file_scheme"
    if re.match(r"^[A-Za-z]:[\\/]", target):
        return "windows_drive_path"
    if target.startswith(("/Users/", "/home/", "/private/", "/tmp/", "/var/", "/opt/")):
        return "unix_local_absolute_path"
    return None


def _scan_markdown_files(docs_dir: Path) -> list[tuple[Path, int, str, str]]:
    violations: list[tuple[Path, int, str, str]] = []
    for md_file in sorted(docs_dir.rglob("*.md")):
        lines = md_file.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, 1):
            if "file://" in line.lower():
                violations.append((md_file, line_no, "file_scheme", line.strip()))
                continue
            targets = [
                match.strip().strip("<>")
                for match in MARKDOWN_LINK_PATTERN.findall(line)
            ]
            for target in targets:
                label = _classify_target(target)
                if label is not None:
                    violations.append((md_file, line_no, label, line.strip()))
                    break
    return violations


def _scan_target_files(files: list[Path]) -> list[tuple[Path, int, str, str]]:
    violations: list[tuple[Path, int, str, str]] = []
    for md_file in sorted(files):
        lines = md_file.read_text(encoding="utf-8").splitlines()
        for line_no, line in enumerate(lines, 1):
            if "file://" in line.lower():
                violations.append((md_file, line_no, "file_scheme", line.strip()))
                continue
            targets = [
                match.strip().strip("<>")
                for match in MARKDOWN_LINK_PATTERN.findall(line)
            ]
            for target in targets:
                label = _classify_target(target)
                if label is not None:
                    violations.append((md_file, line_no, label, line.strip()))
                    break
    return violations


def _resolve_scan_files(docs_dir: Path, files: list[str]) -> list[Path]:
    scan_files: list[Path] = []
    for raw in files:
        candidate = _resolve_project_path(raw)
        if not candidate.exists():
            continue
        if candidate.suffix != ".md":
            continue
        if docs_dir not in candidate.parents:
            continue
        scan_files.append(candidate)
    return sorted(set(scan_files))


def _changed_files_between_revs(
    docs_dir: Path,
    from_rev: str,
    to_rev: str,
) -> list[Path] | None:
    from_rev_result = _run_git_command(
        ["git", "rev-parse", "--verify", f"{from_rev}^{{commit}}"]
    )
    to_rev_result = _run_git_command(
        ["git", "rev-parse", "--verify", f"{to_rev}^{{commit}}"]
    )
    if from_rev_result is None or to_rev_result is None:
        print(
            "docs link check fallback: "
            f"revision check failed ({from_rev}..{to_rev}), scanning all docs"
        )
        return None
    from_ok = from_rev_result.returncode == 0
    to_ok = to_rev_result.returncode == 0
    if not from_ok or not to_ok:
        print(
            "docs link check fallback: "
            f"revision not found ({from_rev}..{to_rev}), scanning all docs"
        )
        return None

    result = _run_git_command(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{from_rev}...{to_rev}"]
    )
    if result is None:
        print("docs link check fallback: git diff command failed, scanning all docs")
        return None
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            print(stderr)
        print("docs link check fallback: git diff failed, scanning all docs")
        return None
    files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return _resolve_scan_files(docs_dir, files)


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--docs-dir",
        default="docs",
        help="Docs root directory to scan",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=[],
        help="Specific markdown files to scan",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Scan changed markdown files between revisions",
    )
    parser.add_argument(
        "--from-rev",
        default="HEAD~1",
        help="Git base revision for --changed-only mode",
    )
    parser.add_argument(
        "--to-rev",
        default="HEAD",
        help="Git target revision for --changed-only mode",
    )
    args = parser.parse_args()
    docs_dir = _resolve_project_path(args.docs_dir)
    if not docs_dir.exists():
        print(f"docs directory not found: {docs_dir}")
        return 2

    scan_files: list[Path] | None = None
    if args.files:
        scan_files = _resolve_scan_files(docs_dir, args.files)
    elif args.changed_only:
        scan_files = _changed_files_between_revs(docs_dir, args.from_rev, args.to_rev)

    if scan_files is None:
        violations = _scan_markdown_files(docs_dir)
    else:
        if not scan_files:
            print(
                f"docs link check skipped: no markdown files selected under {docs_dir}"
            )
            return 0
        violations = _scan_target_files(scan_files)
    if not violations:
        print(f"docs link check passed: {docs_dir}")
        return 0

    print(f"docs link check failed: {len(violations)} issue(s)")
    for path, line_no, label, text in violations:
        print(f"{path}:{line_no}: {label}: {text}")
    return 1


if __name__ == "__main__":
    sys.exit(_main())
