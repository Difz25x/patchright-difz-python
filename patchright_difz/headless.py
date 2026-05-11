from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import patchright

HeadlessSource = Mapping[str, Any]


def get_headless_user_agent(options: HeadlessSource | None = None) -> str | None:
    env = os.environ.get("PATCHRIGHT_DIFZ_HEADLESS_USER_AGENT")

    if env == "0":
        return None
    if env:
        return env

    version = read_chrome_version(options) or read_bundled_chromium_version() or "148.0.0.0"
    major = re.search(r"\d+", version)
    chrome_major = major.group(0) if major else "148"

    return " ".join(
        [
            "Mozilla/5.0",
            f"({platform_token()})",
            "AppleWebKit/537.36",
            "(KHTML, like Gecko)",
            f"Chrome/{chrome_major}.0.0.0",
            "Safari/537.36",
        ]
    )


def with_headless_user_agent(options: HeadlessSource | None) -> dict[str, Any]:
    source = dict(options or {})

    if source.get("headless") is False or source.get("user_agent"):
        return source

    user_agent = get_headless_user_agent(source)
    if user_agent:
        source["user_agent"] = user_agent

    return source


def with_default_user_agent(
    options: HeadlessSource | None,
    user_agent: str | None,
) -> dict[str, Any]:
    source = dict(options or {})

    if user_agent and not source.get("user_agent"):
        source["user_agent"] = user_agent

    return source


def read_chrome_version(options: HeadlessSource | None = None) -> str | None:
    source = options or {}
    executable_path = source.get("executable_path")

    if isinstance(executable_path, (str, Path)):
        return read_executable_version(str(executable_path))

    channel = source.get("channel")
    channel_name = channel if isinstance(channel, str) else ""

    for path in chrome_paths(channel_name.lower()):
        if Path(path).exists():
            version = read_executable_version(path)
            if version:
                return version

    return None


def read_executable_version(path: str) -> str | None:
    if sys.platform == "win32":
        return read_windows_file_version(path)

    result = subprocess.run(
        [path, "--version"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return parse_version(f"{result.stdout or ''} {result.stderr or ''}")


def read_windows_file_version(path: str) -> str | None:
    script = f"(Get-Item -LiteralPath {json.dumps(path)}).VersionInfo.ProductVersion"

    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    return parse_version(result.stdout)


def chrome_paths(channel: str) -> list[str]:
    if sys.platform != "win32":
        if "edge" in channel:
            return ["microsoft-edge", "microsoft-edge-stable"]

        return ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]

    program_files = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LocalAppData"),
    ]
    bases = [base for base in program_files if base]

    if "edge" in channel:
        return [
            str(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
            for base in bases
        ]

    local_app_data = os.environ.get("LocalAppData", "")

    if "canary" in channel:
        return [
            str(
                Path(local_app_data)
                / "Google"
                / "Chrome SxS"
                / "Application"
                / "chrome.exe"
            )
        ]

    if "beta" in channel:
        return [
            str(Path(base) / "Google" / "Chrome Beta" / "Application" / "chrome.exe")
            for base in bases
        ]

    if "dev" in channel:
        return [
            str(Path(base) / "Google" / "Chrome Dev" / "Application" / "chrome.exe")
            for base in bases
        ]

    return [
        str(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
        for base in bases
    ]


def read_bundled_chromium_version() -> str | None:
    try:
        browsers_path = Path(patchright.__file__).parent / "driver" / "package" / "browsers.json"
        data = json.loads(browsers_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None

    for browser in data.get("browsers", []):
        if browser.get("name") == "chromium":
            version = browser.get("browserVersion")
            return version if isinstance(version, str) else None

    return None


def parse_version(value: str) -> str | None:
    match = re.search(r"\d+(?:\.\d+){1,3}", value)
    return match.group(0) if match else None


def platform_token() -> str:
    if sys.platform == "darwin":
        return "Macintosh; Intel Mac OS X 10_15_7"
    if sys.platform.startswith("linux"):
        return "X11; Linux x86_64"

    return "Windows NT 10.0; Win64; x64"
