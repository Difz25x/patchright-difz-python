#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=ROOT, text=True)

    if result.returncode != 0:
        raise SystemExit(result.returncode)

    return result


def output(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
    )

    if result.returncode != 0:
        return ""

    return result.stdout.strip()


def has_staged_changes() -> bool:
    result = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)

    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True

    raise SystemExit(result.returncode)


def version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def ensure_tag(tag: str) -> None:
    current = output(["git", "rev-parse", "HEAD"])
    tagged = output(["git", "rev-list", "-n", "1", tag])

    if not tagged:
        run(["git", "tag", tag])
        return

    if tagged != current:
        print(f"{tag} already exists on another commit.", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tag = f"v{version()}"

    run([sys.executable, "-m", "compileall", "patchright_difz"])
    run([sys.executable, "-m", "build"])

    if args.dry_run:
        print(f"[dry-run] would commit, tag {tag}, and push to GitHub.")
        print("[dry-run] GitHub Actions would publish the package to PyPI.")
        return

    run(["git", "add", "-A"])

    if has_staged_changes():
        run(["git", "commit", "-m", f"Release {tag}"])

    ensure_tag(tag)
    run(["git", "push", "origin", "HEAD"])
    run(["git", "push", "origin", tag])

    print(f"{tag} pushed. GitHub Actions will publish to PyPI.")


if __name__ == "__main__":
    main()
