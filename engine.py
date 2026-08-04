"""Ensure Tomato engine binary exists (auto-download, no exe in git)."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import ssl
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

PLUGIN_DIR = Path(__file__).resolve().parent
BIN_DIR = PLUGIN_DIR / "bin"

# Pinned to vendored third_party snapshot / upstream tag.
DEFAULT_ENGINE_VERSION = "v2.4.13"
DEFAULT_UPSTREAM_OWNER_REPO = "zhongbai2333/Tomato-Novel-Downloader"

LogFn = Callable[[str], None]


def _noop_log(msg: str) -> None:
    del msg


def local_engine_path() -> Path:
    name = "tomato-novel-downloader.exe" if os.name == "nt" else "tomato-novel-downloader"
    return BIN_DIR / name


def detect_platform() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        arch = "amd64"
    elif machine in {"aarch64", "arm64"}:
        arch = "arm64"
    elif machine in {"armv7l", "armv7", "arm"}:
        arch = "arm32"
    else:
        arch = machine
    if system.startswith("win"):
        return "windows", arch
    if system == "darwin":
        return "macos", arch
    return "linux", arch


def upstream_asset_name(version: str, system: str, arch: str) -> str:
    """Map host to upstream Tomato release asset names."""
    ver = version.lstrip("v")
    tag_ver = version if version.startswith("v") else f"v{version}"
    # Prefer tag-style suffix used by upstream releases (v2.4.13).
    suffix = tag_ver
    if system == "windows" and arch == "amd64":
        return f"TomatoNovelDownloader-Win64-{suffix}.exe"
    if system == "windows" and arch == "arm64":
        return f"TomatoNovelDownloader-WinArm64-{suffix}.exe"
    if system == "linux" and arch == "amd64":
        return f"TomatoNovelDownloader-Linux_amd64-{suffix}"
    if system == "linux" and arch == "arm64":
        return f"TomatoNovelDownloader-Linux_arm64-{suffix}"
    if system == "macos" and arch == "amd64":
        return f"TomatoNovelDownloader-macOS_amd64-{suffix}"
    if system == "macos" and arch == "arm64":
        return f"TomatoNovelDownloader-macOS_arm64-{suffix}"
    raise RuntimeError(
        f"当前平台暂无自动下载映射: {system}/{arch}（引擎版本 {ver}）。"
        "请手动配置 downloader.tomato_exe，或按 BUILD_TOMATO.md 源码构建。"
    )


def default_download_url(version: str, owner_repo: str | None = None) -> str:
    system, arch = detect_platform()
    asset = upstream_asset_name(version, system, arch)
    repo = owner_repo or DEFAULT_UPSTREAM_OWNER_REPO
    tag = version if version.startswith("v") else f"v{version}"
    return f"https://github.com/{repo}/releases/download/{tag}/{asset}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download(url: str, dest: Path, log: LogFn) -> None:
    log(f"正在下载引擎: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "maibot-fanqie-novel-downloader/1.4"},
        method="GET",
    )
    fd, tmp_name = tempfile.mkstemp(prefix="tomato-engine-", dir=str(dest.parent))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                shutil.copyfileobj(resp, out, length=1024 * 1024)
        tmp_path.replace(dest)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def ensure_engine(
    *,
    exe: Path | None = None,
    auto_fetch: bool = True,
    download_url: str = "",
    version: str = DEFAULT_ENGINE_VERSION,
    expected_sha256: str = "",
    owner_repo: str = DEFAULT_UPSTREAM_OWNER_REPO,
    log: LogFn | None = None,
) -> Path:
    """
    Return a usable engine path.

    Prefer an existing configured/local binary; otherwise download from
    GitHub Releases (upstream Tomato assets by default). Never commits exe to git.
    """
    logger = log or _noop_log
    target = Path(exe) if exe else local_engine_path()

    if target.is_file() and target.stat().st_size > 0:
        return target

    # Also accept common local names under bin/
    for candidate in (
        local_engine_path(),
        BIN_DIR / "tomato-novel-downloader",
        BIN_DIR / "tomato-novel-downloader.exe",
        BIN_DIR / f"TomatoNovelDownloader-Win64-{version}.exe",
        BIN_DIR / f"TomatoNovelDownloader-Linux_amd64-{version}",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate

    if not auto_fetch:
        raise FileNotFoundError(
            f"缺少本机引擎: {target}。已关闭自动下载，请按 BUILD_TOMATO.md 构建，"
            "或开启 downloader.auto_fetch_engine。"
        )

    url = (download_url or "").strip() or default_download_url(version, owner_repo)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    final_path = local_engine_path()

    try:
        _download(url, final_path, logger)
    except urllib.error.HTTPError as exc:
        raise FileNotFoundError(
            f"自动下载引擎失败 HTTP {exc.code}: {url}\n"
            "可配置 downloader.engine_download_url 使用镜像，或本机执行 "
            "`python scripts/build_tomato.py`。"
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise FileNotFoundError(
            f"自动下载引擎失败: {exc}\nURL: {url}\n"
            "可配置镜像 URL，或按 BUILD_TOMATO.md 源码构建。"
        ) from exc

    if os.name != "nt":
        mode = final_path.stat().st_mode
        final_path.chmod(mode | 0o111)

    if expected_sha256.strip():
        got = _sha256_file(final_path)
        want = expected_sha256.strip().lower()
        if got.lower() != want:
            final_path.unlink(missing_ok=True)
            raise FileNotFoundError(
                f"引擎校验失败: sha256={got} expected={want}"
            )

    size = final_path.stat().st_size
    logger(f"引擎已就绪: {final_path} ({size} bytes)")
    return final_path
