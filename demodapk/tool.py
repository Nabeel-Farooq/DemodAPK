"""
APK tool utilities module.

Provides:
- Safe concurrent file downloads
- Progress tracking with Rich
- GitHub release fetching
- SHA256 verification
- APKEditor downloader
"""

from __future__ import annotations

import json
import os
import hashlib
import re
import signal
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Event
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from rich.align import Align
from rich.panel import Panel
from rich.progress import (
    Progress,
    BarColumn,
    DownloadColumn,
    TaskID,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from demodapk.utils import console


# =========================
# Exceptions
# =========================

class DownloadError(Exception):
    pass


class ChecksumError(Exception):
    pass


class ReleaseFetchError(Exception):
    pass


# =========================
# Models
# =========================

@dataclass(slots=True)
class ReleaseInfo:
    version: str
    url: str
    sha256: str | None = None


@dataclass(slots=True)
class DownloadResult:
    url: str
    path: Path
    size: int


# =========================
# Progress setup
# =========================

progress = Progress(
    DownloadColumn(),
    "•",
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",
    "•",
    TransferSpeedColumn(),
    "•",
    TimeRemainingColumn(),
    console=console,
)

done_event = Event()


def handle_sigint(*_) -> None:
    done_event.set()


signal.signal(signal.SIGINT, handle_sigint)


# =========================
# Helpers
# =========================

def _filename_from_url(url: str) -> str:
    return Path(urlparse(url).path).name or "download.bin"


def get_file_sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


# =========================
# Core download
# =========================

def download_file(
    task_id: TaskID,
    url: str,
    dest: Path,
    *,
    timeout: int = 30,
) -> DownloadResult:
    """
    Download a single file safely (atomic write).
    """

    tmp = dest.with_suffix(".part")

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urlopen(req, timeout=timeout) as response:
            total = response.headers.get("Content-Length")
            total = int(total) if total else 0

            progress.update(task_id, total=total)
            progress.start_task(task_id)

            with open(tmp, "wb") as f:
                while True:
                    if done_event.is_set():
                        raise DownloadError("Download cancelled")

                    chunk = response.read(1024 * 64)
                    if not chunk:
                        break

                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

        tmp.replace(dest)

        return DownloadResult(
            url=url,
            path=dest,
            size=dest.stat().st_size,
        )

    except (URLError, HTTPError) as e:
        raise DownloadError(str(e)) from e


# =========================
# Batch download
# =========================

def download(
    urls: list[str],
    dest_dir: Path,
    *,
    workers: int = 4,
) -> list[DownloadResult]:

    dest_dir.mkdir(parents=True, exist_ok=True)

    results: list[DownloadResult] = []

    with progress:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []

            for url in urls:
                filename = _filename_from_url(url)
                path = dest_dir / filename

                task = progress.add_task("download", filename=filename, start=False)

                futures.append(
                    pool.submit(download_file, task, url, path)
                )

            for f in as_completed(futures):
                results.append(f.result())

    return results


# =========================
# GitHub release
# =========================

def get_latest_apkeditor_info() -> ReleaseInfo | None:
    url = "https://api.github.com/repos/reandroid/apkeditor/releases/latest"

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})

        with urlopen(req, timeout=30) as resp:
            data = json.load(resp)

        tag = data.get("tag_name")
        if not tag:
            return None

        version = tag.lstrip("Vv")

        release = ReleaseInfo(version=version, url="")

        assets = data.get("assets", [])
        jar = f"APKEditor-{version}.jar"

        for asset in assets:
            if asset.get("name") == jar:
                release.url = asset.get("browser_download_url", "")
                digest = asset.get("digest")

                if digest and digest.startswith("sha256:"):
                    release.sha256 = digest.split(":")[1]

                break

        if not release.sha256:
            body = data.get("body", "")
            match = re.search(r"([a-fA-F0-9]{64})", body)
            if match:
                release.sha256 = match.group(1)

        if not release.url:
            return None

        return release

    except (URLError, HTTPError) as e:
        raise ReleaseFetchError(str(e)) from e


# =========================
# APKEditor download
# =========================

def download_apkeditor(dest_dir: Path) -> DownloadResult | None:

    release = get_latest_apkeditor_info()
    if not release:
        raise ReleaseFetchError("Unable to fetch release info")

    console.print(
        Panel(
            Align.center(f"APKEditor v{release.version}"),
            style="bold cyan",
        )
    )

    results = download([release.url], dest_dir)
    result = results[0]

    if release.sha256:
        actual = get_file_sha256(result.path)

        if actual != release.sha256:
            raise ChecksumError(
                f"Checksum mismatch:\nexpected={release.sha256}\nactual={actual}"
            )

    return result
