#!/usr/bin/env python3
"""Verified, user-space self-updater for MLBB Link Emulator Tools."""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath
from typing import Any, Callable

VERSION = "0.15.0"
MANIFEST_URL = "https://raw.githubusercontent.com/AndrewHorrison/mlbb-link-cloud-build/main/updates/emulator-latest.json"
RELEASE_PREFIX = "https://github.com/AndrewHorrison/mlbb-link-cloud-build/releases/download/"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_SINGLE_FILE_BYTES = 8 * 1024 * 1024


def version_tuple(value: str) -> tuple[int, ...]:
    bits = value.strip().lstrip("v").split(".")
    if not bits or any(not part.isdigit() for part in bits):
        raise ValueError(f"Unsupported version format: {value!r}")
    return tuple(int(part) for part in bits)


def is_newer(remote: str, local: str = VERSION) -> bool:
    left, right = version_tuple(remote), version_tuple(local)
    size = max(len(left), len(right))
    return left + (0,) * (size - len(left)) > right + (0,) * (size - len(right))


def _request(url: str, timeout: float = 10.0):
    request = urllib.request.Request(url, headers={"User-Agent": "MLBB-Link-Emulator-Updater/1.0", "Accept": "application/json"})
    return urllib.request.urlopen(request, timeout=timeout)


def check_for_update(current_version: str = VERSION, manifest_url: str = MANIFEST_URL) -> dict[str, Any] | None:
    if manifest_url != MANIFEST_URL:
        raise ValueError("Custom update manifest URLs are not allowed")
    with _request(manifest_url, 6.0) as response:
        if response.status != 200:
            raise RuntimeError(f"Update manifest returned HTTP {response.status}")
        body = response.read(128 * 1024)
    manifest = json.loads(body.decode("utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("Update manifest is not a JSON object")
    remote_version = str(manifest.get("version", ""))
    asset_url = str(manifest.get("assetUrl", ""))
    digest = str(manifest.get("sha256", "")).lower()
    if not remote_version or not asset_url or not is_newer(remote_version, current_version):
        return None
    if not asset_url.startswith(RELEASE_PREFIX) or "/MLBB-Link-Emulator-Tools.tar.gz" not in asset_url:
        raise ValueError("The update asset is not a trusted versioned GitHub release URL")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("The update manifest SHA-256 is invalid")
    return manifest


def _read_package_manifest(archive: tarfile.TarFile) -> dict[str, Any]:
    for member in archive.getmembers():
        clean = member.name.removeprefix("./")
        if clean == "package.json" and member.isfile() and not member.issym() and not member.islnk():
            stream = archive.extractfile(member)
            if stream is None:
                break
            value = json.loads(stream.read(64 * 1024).decode("utf-8"))
            if isinstance(value, dict):
                return value
    raise ValueError("The downloaded update is missing package.json")


def download_and_install_update(manifest: dict[str, Any], install_root: str | Path,
                                progress: Callable[[int], None] | None = None) -> str:
    """Download, hash-check, safely stage, and atomically replace whitelisted app files.

    This routine writes only into the current user's application directory. It never uses sudo,
    executes files from the archive, follows archive symlinks, or writes outside install_root.
    """
    version = str(manifest.get("version", ""))
    url = str(manifest.get("assetUrl", ""))
    expected = str(manifest.get("sha256", "")).lower()
    if not version or not is_newer(version, VERSION):
        raise ValueError("This update is not newer than the installed version")
    if not url.startswith(RELEASE_PREFIX) or "/MLBB-Link-Emulator-Tools.tar.gz" not in url:
        raise ValueError("Untrusted update URL")
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise ValueError("Invalid update checksum")

    with _request(url, 30.0) as response:
        if response.status != 200:
            raise RuntimeError(f"Update download returned HTTP {response.status}")
        advertised = response.headers.get("Content-Length")
        if advertised and int(advertised) > MAX_ARCHIVE_BYTES:
            raise ValueError("Update archive is larger than the allowed limit")
        payload = response.read(MAX_ARCHIVE_BYTES + 1)
    if not payload or len(payload) > MAX_ARCHIVE_BYTES:
        raise ValueError("Update archive is empty or exceeds the allowed size")
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError("SHA-256 verification failed; nothing was installed")
    if progress:
        progress(30)

    root = Path(install_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    stage_parent = root.parent
    stage = Path(tempfile.mkdtemp(prefix=".mlbb-emulator-update-", dir=stage_parent))
    backup = stage / "backup"
    staged = stage / "staged"
    backup.mkdir()
    staged.mkdir()
    changed: list[str] = []
    try:
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
            package = _read_package_manifest(archive)
            if str(package.get("version")) != version:
                raise ValueError("Package version does not match the signed update manifest")
            listed = package.get("files")
            if not isinstance(listed, list) or not listed:
                raise ValueError("Update package does not provide an allowed-file list")
            whitelist = {str(x) for x in listed}
            if "package.json" not in whitelist or "launcher.py" not in whitelist:
                raise ValueError("Update package is missing required app files")
            total = 0
            seen: set[str] = set()
            for member in archive.getmembers():
                clean = member.name.removeprefix("./")
                if not clean or clean == "." or member.isdir():
                    continue
                pure = PurePosixPath(clean)
                if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
                    raise ValueError(f"Unsafe archive path: {member.name}")
                if clean not in whitelist:
                    raise ValueError(f"Archive contains an unlisted file: {clean}")
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError(f"Non-regular archive entry rejected: {clean}")
                if member.size < 0 or member.size > MAX_SINGLE_FILE_BYTES:
                    raise ValueError(f"File size limit exceeded: {clean}")
                total += member.size
                if total > 25 * 1024 * 1024:
                    raise ValueError("Unpacked update exceeds the allowed size")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError(f"Cannot read archive member {clean}")
                output = staged / clean
                output.write_bytes(stream.read(MAX_SINGLE_FILE_BYTES + 1))
                if output.stat().st_size != member.size:
                    raise ValueError(f"Archive member size mismatch: {clean}")
                seen.add(clean)
            missing = whitelist - seen
            if missing:
                raise ValueError("Update is missing package files: " + ", ".join(sorted(missing)))
        if progress:
            progress(65)

        # Back up current versions first so a filesystem error can roll back changed modules.
        for name in sorted(whitelist):
            current = root / name
            if current.exists():
                if not current.is_file() or current.is_symlink():
                    raise ValueError(f"Refusing to replace non-regular install target: {name}")
                shutil.copy2(current, backup / name)
        try:
            for name in sorted(whitelist):
                os.replace(staged / name, root / name)
                changed.append(name)
            if progress:
                progress(100)
        except Exception:
            for name in reversed(changed):
                old = backup / name
                target = root / name
                if old.exists():
                    os.replace(old, target)
                else:
                    target.unlink(missing_ok=True)
            raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return version
