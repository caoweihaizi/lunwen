from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
import time


@dataclass(frozen=True)
class DownloadResult:
    path: Path
    sha256: str
    byte_size: int
    final_url: str
    retrieved_at_utc: str
    reused: bool
    headers: dict


def byte_ranges(total_size: int, parts: int):
    if total_size <= 0 or parts <= 0:
        raise ValueError("sizes must be positive")
    part_size = (total_size + parts - 1) // parts
    return [(start, min(start + part_size - 1, total_size - 1)) for start in range(0, total_size, part_size)]


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_download(url: str, target: Path, expected_sha256: str = None, timeout: int = 60):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        actual = file_sha256(target)
        if expected_sha256 and actual == expected_sha256:
            return DownloadResult(target, actual, target.stat().st_size, url, "", True, {})
        if expected_sha256:
            raise ValueError(f"existing file hash mismatch: {target}")

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".part", delete=False) as out:
            temp_path = Path(out.name)
            request = urllib.request.Request(url, headers={"User-Agent": "MUCAR-research/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                digest = hashlib.sha256()
                size = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                out.flush()
                os.fsync(out.fileno())
                final_url = response.geturl()
                headers = dict(response.headers.items())
        actual = digest.hexdigest()
        if expected_sha256 and actual != expected_sha256:
            raise ValueError(f"download hash mismatch for {url}")
        os.replace(temp_path, target)
        return DownloadResult(
            target, actual, size, final_url,
            datetime.now(timezone.utc).isoformat(), False, headers,
        )
    except Exception:
        if temp_path and temp_path.exists():
            temp_path.unlink()
        raise


def parallel_range_download(url: str, target: Path, total_size: int, workers: int = 8, timeout: int = 120):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    work_dir = target.parent / f".{target.name}.parts"
    work_dir.mkdir(exist_ok=True)
    ranges = byte_ranges(total_size, workers)

    def fetch(item):
        index, (start, end) = item
        part = work_dir / f"part-{index:04d}"
        expected_size = end - start + 1
        if part.exists() and part.stat().st_size == expected_size:
            return part
        for attempt in range(3):
            request = urllib.request.Request(url, headers={
                "User-Agent": "MUCAR-research/1.0",
                "Range": f"bytes={start}-{end}",
            })
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response, part.open("wb") as out:
                    if response.status != 206:
                        raise ValueError(f"server ignored range request: HTTP {response.status}")
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
                if part.stat().st_size != expected_size:
                    raise ValueError(f"incomplete range {start}-{end}")
                return part
            except Exception:
                part.unlink(missing_ok=True)
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        parts = list(executor.map(fetch, enumerate(ranges)))

    temp = target.parent / f".{target.name}.assembling"
    digest = hashlib.sha256()
    size = 0
    try:
        with temp.open("wb") as out:
            for part in parts:
                with part.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        out.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            out.flush()
            os.fsync(out.fileno())
        if size != total_size:
            raise ValueError(f"assembled size mismatch: {size} != {total_size}")
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    for part in parts:
        part.unlink()
    work_dir.rmdir()
    return DownloadResult(
        target, digest.hexdigest(), size, url,
        datetime.now(timezone.utc).isoformat(), False, {"Content-Length": str(total_size)},
    )
