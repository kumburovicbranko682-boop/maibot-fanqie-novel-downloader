"""Ensure Tomato engine binary exists (auto-download, no exe in git)."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import ssl
import subprocess
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


def _glibc_too_old_for_gnu() -> bool:
    """Heuristic: GNU glib builds of Tomato need newer glibc (e.g. 2.39)."""
    try:
        out = subprocess.check_output(["ldd", "--version"], stderr=subprocess.STDOUT, text=True)
        # "ldd (Debian GLIBC 2.36-9...) 2.36"
        import re

        m = re.search(r"(\d+)\.(\d+)", out.splitlines()[0] if out else "")
        if not m:
            return True
        major, minor = int(m.group(1)), int(m.group(2))
        # Prefer musl when host glibc < 2.39
        return (major, minor) < (2, 39)
    except Exception:
        return True


def prefer_musl() -> bool:
    system, _arch = detect_platform()
    if system != "linux":
        return False
    return _glibc_too_old_for_gnu()


def upstream_asset_name(
    version: str, system: str, arch: str, *, musl: bool = False
) -> str:
    """Map host to upstream Tomato release asset names."""
    ver = version.lstrip("v")
    tag_ver = version if version.startswith("v") else f"v{version}"
    suffix = tag_ver
    if system == "windows" and arch == "amd64":
        return f"TomatoNovelDownloader-Win64-{suffix}.exe"
    if system == "windows" and arch == "arm64":
        return f"TomatoNovelDownloader-WinArm64-{suffix}.exe"
    if system == "linux" and arch == "amd64":
        if musl:
            return f"TomatoNovelDownloader-Linux_musl_amd64-{suffix}"
        return f"TomatoNovelDownloader-Linux_amd64-{suffix}"
    if system == "linux" and arch == "arm64":
        if musl:
            return f"TomatoNovelDownloader-Linux_musl_arm64-{suffix}"
        return f"TomatoNovelDownloader-Linux_arm64-{suffix}"
    if system == "macos" and arch == "amd64":
        return f"TomatoNovelDownloader-macOS_amd64-{suffix}"
    if system == "macos" and arch == "arm64":
        return f"TomatoNovelDownloader-macOS_arm64-{suffix}"
    raise RuntimeError(
        f"当前平台暂无自动下载映射: {system}/{arch}（引擎版本 {ver}）。"
        "请手动配置 downloader.tomato_exe，或按 BUILD_TOMATO.md 源码构建。"
    )


def default_download_url(
    version: str, owner_repo: str | None = None, *, musl: bool | None = None
) -> str:
    system, arch = detect_platform()
    use_musl = prefer_musl() if musl is None else musl
    asset = upstream_asset_name(version, system, arch, musl=use_musl)
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


def probe_engine(exe: Path) -> tuple[bool, str]:
    """Return (ok, detail). ok means binary can at least start."""
    if not exe.is_file():
        return False, f"missing: {exe}"
    try:
        proc = subprocess.run(
            [str(exe), "--help"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except subprocess.TimeoutExpired:
        # UI apps may hang on --help; treat as runnable if it started.
        return True, "timeout on --help (assumed ok)"
    except OSError as exc:
        return False, str(exc)
    err = (proc.stderr or "") + (proc.stdout or "")
    if "GLIBC_" in err and "not found" in err:
        return False, err.strip()[:500]
    if proc.returncode not in (0, 1, 2) and "GLIBC_" in err:
        return False, err.strip()[:500]
    # Many CLIs return 0/1/2 for help; loader failures usually non-zero with GLIBC text.
    if "not found" in err and "libc" in err.lower():
        return False, err.strip()[:500]
    return True, err.strip()[:200] or f"exit={proc.returncode}"


def _fetch_to(
    *,
    dest: Path,
    version: str,
    owner_repo: str,
    download_url: str,
    expected_sha256: str,
    musl: bool | None,
    log: LogFn,
) -> Path:
    url = (download_url or "").strip() or default_download_url(
        version, owner_repo, musl=musl
    )
    _download(url, dest, log)
    if os.name != "nt":
        mode = dest.stat().st_mode
        dest.chmod(mode | 0o111)
    if expected_sha256.strip():
        got = _sha256_file(dest)
        want = expected_sha256.strip().lower()
        if got.lower() != want:
            dest.unlink(missing_ok=True)
            raise FileNotFoundError(f"引擎校验失败: sha256={got} expected={want}")
    log(f"引擎已就绪: {dest} ({dest.stat().st_size} bytes)")
    return dest


def ensure_engine(
    *,
    exe: Path | None = None,
    auto_fetch: bool = True,
    download_url: str = "",
    version: str = DEFAULT_ENGINE_VERSION,
    expected_sha256: str = "",
    owner_repo: str = DEFAULT_UPSTREAM_OWNER_REPO,
    log: LogFn | None = None,
    force_refetch: bool = False,
) -> Path:
    """
    Return a usable engine path.

    Prefer an existing configured/local binary; otherwise download from
    GitHub Releases (upstream Tomato assets by default). On Linux hosts with
    older glibc, prefer the musl build. Never commits exe to git.
    """
    logger = log or _noop_log
    target = Path(exe) if exe else local_engine_path()
    final_path = local_engine_path()

    candidates: list[Path] = []
    if not force_refetch:
        candidates.append(target)
        candidates.extend(
            [
                local_engine_path(),
                BIN_DIR / "tomato-novel-downloader",
                BIN_DIR / "tomato-novel-downloader.exe",
                BIN_DIR / f"TomatoNovelDownloader-Win64-{version}.exe",
                BIN_DIR / f"TomatoNovelDownloader-Linux_musl_amd64-{version}",
                BIN_DIR / f"TomatoNovelDownloader-Linux_amd64-{version}",
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if not (candidate.is_file() and candidate.stat().st_size > 0):
            continue
        ok, detail = probe_engine(candidate)
        if ok:
            return candidate
        logger(f"引擎不可用，将尝试替换: {candidate} ({detail})")
        # If broken binary sits at the default path, remove so we can refetch.
        if candidate.resolve() == final_path.resolve():
            try:
                candidate.unlink()
            except Exception:
                pass

    if not auto_fetch:
        raise FileNotFoundError(
            f"缺少可用本机引擎: {target}。已关闭自动下载，请按 BUILD_TOMATO.md 构建，"
            "或开启 downloader.auto_fetch_engine。"
        )

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    custom = (download_url or "").strip()
    try_order: list[bool | None]
    if custom:
        try_order = [None]  # honor explicit URL once
    elif prefer_musl():
        try_order = [True, False]
    else:
        try_order = [False, True]

    last_err: Exception | None = None
    for musl_flag in try_order:
        try:
            if custom:
                path = _fetch_to(
                    dest=final_path,
                    version=version,
                    owner_repo=owner_repo,
                    download_url=custom,
                    expected_sha256=expected_sha256,
                    musl=None,
                    log=logger,
                )
            else:
                path = _fetch_to(
                    dest=final_path,
                    version=version,
                    owner_repo=owner_repo,
                    download_url="",
                    expected_sha256=expected_sha256,
                    musl=musl_flag,
                    log=logger,
                )
            ok, detail = probe_engine(path)
            if ok:
                return path
            logger(f"下载到的引擎仍不可用: {detail}")
            path.unlink(missing_ok=True)
            last_err = RuntimeError(detail)
            if custom:
                break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if custom:
                break

    raise FileNotFoundError(
        f"自动准备引擎失败: {last_err}\n"
        "Linux 老系统请使用 musl 构建；也可配置 downloader.engine_download_url。"
    )
