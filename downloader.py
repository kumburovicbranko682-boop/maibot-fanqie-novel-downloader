"""本机签名网关下载核心。"""

from __future__ import annotations

import http.cookiejar
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .engine import ensure_engine


ProgressCallback = Callable[[dict[str, Any]], None]


class LocalSignerGateway:
    def __init__(self, base: str, password: str) -> None:
        self.base = base.rstrip("/")
        self.password = password
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )

    def call(self, method: str, path: str, data: Any = None, timeout: int = 60) -> Any:
        url = self.base + path
        headers = {"User-Agent": "maibot-fanqie/1.0", "Accept": "application/json"}
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with self.opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except Exception:
                return raw.decode("utf-8", "replace")

    def login(self) -> None:
        data = self.call("POST", "/api/login", {"password": self.password})
        if not (isinstance(data, dict) and data.get("ok")):
            raise RuntimeError(f"本地网关登录失败: {data}")

    def wait_ready(self, seconds: float = 45, proc: subprocess.Popen | None = None) -> None:
        deadline = time.time() + seconds
        last: Exception | None = None
        while time.time() < deadline:
            if proc is not None and proc.poll() is not None:
                raise RuntimeError(
                    f"本机引擎进程已退出 code={proc.returncode}，网关未能启动"
                )
            try:
                urllib.request.urlopen(self.base + "/", timeout=2).read(32)
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(0.4)
        raise RuntimeError(f"本地签名网关未就绪: {last}")


def ensure_local_signer(
    exe: Path,
    data_dir: Path,
    password: str,
    addr: str,
    *,
    auto_fetch: bool = True,
    download_url: str = "",
    engine_version: str = "v2.4.13",
    engine_sha256: str = "",
) -> subprocess.Popen | None:
    try:
        urllib.request.urlopen(addr + "/", timeout=2).read(32)
        return None
    except Exception:
        pass

    def _log(msg: str) -> None:
        print(f"[fanqie-engine] {msg}", flush=True)

    def _err_tail(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")[-1200:]
        except Exception:
            return ""

    exe = ensure_engine(
        exe=exe,
        auto_fetch=auto_fetch,
        download_url=download_url,
        version=engine_version,
        expected_sha256=engine_sha256,
        log=_log,
    )
    if not exe.exists():
        raise FileNotFoundError(f"缺少本机引擎: {exe}。")

    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "server.stdout.log"
    stderr_path = log_dir / "server.stderr.log"
    stdout_f = open(stdout_path, "ab", buffering=0)
    stderr_f = open(stderr_path, "ab", buffering=0)
    env = os.environ.copy()
    env["TOMATO_WEB_ADDR"] = addr.replace("http://", "").replace("https://", "")
    # Pin the engine binary: skip Tomato's same-tag SHA256 hotfix replace.
    # Honored by vendored third_party builds; also sets CARGO so stock upstream
    # Release binaries (which treat CARGO as cargo-run) skip the same path.
    env.setdefault("TOMATO_DISABLE_HOTFIX", "1")
    env.setdefault("CARGO", "maibot-fanqie-plugin")

    def _start(binary: Path) -> subprocess.Popen:
        p = subprocess.Popen(
            [str(binary), "--server", "--data-dir", str(data_dir), "--password", password],
            env=env,
            stdout=stdout_f,
            stderr=stderr_f,
        )
        p._tomato_log_handles = (stdout_f, stderr_f)  # type: ignore[attr-defined]
        return p

    proc = _start(exe)
    time.sleep(0.8)
    if proc.poll() is None:
        return proc

    err_tail = _err_tail(stderr_path)
    # Broken glibc-linked binary: force refetch (prefers musl on old hosts).
    if auto_fetch and ("GLIBC_" in err_tail or "libc.so" in err_tail):
        _log(f"引擎启动失败，强制重拉兼容构建: {err_tail.strip()[:240]}")
        try:
            exe.unlink(missing_ok=True)
        except Exception:
            pass
        exe = ensure_engine(
            exe=exe,
            auto_fetch=True,
            download_url="",
            version=engine_version,
            expected_sha256="",
            log=_log,
            force_refetch=True,
        )
        proc = _start(exe)
        time.sleep(0.8)
        if proc.poll() is None:
            return proc
        err_tail = _err_tail(stderr_path)

    raise RuntimeError(
        f"本机引擎无法启动（已退出 code={proc.returncode}）。"
        f"详情: {err_tail.strip() or '无 stderr'}。"
        " Linux 老系统需 musl 构建；可配置 downloader.engine_download_url。"
    )


def download_book(
    book_id: str,
    *,
    exe: Path,
    data_dir: Path,
    output_dir: Path,
    addr: str,
    password: str,
    workers: int = 6,
    progress: ProgressCallback | None = None,
    stop_server: bool = True,
    auto_fetch: bool = True,
    download_url: str = "",
    engine_version: str = "v2.4.13",
    engine_sha256: str = "",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    proc = ensure_local_signer(
        exe,
        data_dir,
        password,
        addr,
        auto_fetch=auto_fetch,
        download_url=download_url,
        engine_version=engine_version,
        engine_sha256=engine_sha256,
    )
    gw = LocalSignerGateway(addr, password)
    try:
        gw.wait_ready(proc=proc)
        gw.login()
        full = gw.call("GET", "/api/config/full")
        if not isinstance(full, dict):
            raise RuntimeError(f"读配置失败: {full}")
        full.update(
            {
                "save_path": str(output_dir),
                "novel_format": "txt",
                "use_official_api": False,
                "api_endpoints": [],
                "max_workers": max(1, int(workers)),
                "ask_format_after_download": False,
                "min_wait_time": min(int(full.get("min_wait_time") or 1000), 300),
                "max_wait_time": min(int(full.get("max_wait_time") or 1200), 800),
            }
        )
        gw.call("POST", "/api/config/full", full)

        before = {p.resolve() for p in output_dir.glob("*.txt")}
        job = gw.call("POST", "/api/jobs", {"book_id": book_id})
        if not isinstance(job, dict) or "id" not in job:
            raise RuntimeError(f"创建任务失败: {job}")
        job_id = job["id"]
        if progress:
            progress({"state": "queued", "job_id": job_id, "book_id": book_id})

        while True:
            data = gw.call("GET", "/api/jobs")
            items = (data or {}).get("items") if isinstance(data, dict) else []
            cur = next((x for x in items if x.get("id") == job_id), None)
            if not cur:
                raise RuntimeError("任务消失")
            prog = cur.get("progress") or {}
            if progress:
                progress(
                    {
                        "state": cur.get("state"),
                        "job_id": job_id,
                        "book_id": book_id,
                        "title": cur.get("title"),
                        "saved": prog.get("saved_chapters"),
                        "total": prog.get("chapter_total"),
                    }
                )
            if cur.get("format_options"):
                gw.call("POST", f"/api/jobs/{job_id}/format", {"format": "txt"})
            if cur.get("book_name_options"):
                opts = cur["book_name_options"]
                gw.call(
                    "POST",
                    f"/api/jobs/{job_id}/book_name",
                    {"book_name": opts[0]},
                )
            state = cur.get("state")
            if state in ("done", "finished", "completed", "success"):
                break
            if state in ("failed", "error", "cancelled"):
                raise RuntimeError(f"任务失败: {cur}")
            time.sleep(3)

        after = sorted(
            output_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        for path in after:
            if path.resolve() not in before or len(after) == 1:
                return path
        cwd_txts = sorted(
            Path.cwd().glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if cwd_txts and (time.time() - cwd_txts[0].stat().st_mtime) < 600:
            dest = output_dir / cwd_txts[0].name
            dest.write_bytes(cwd_txts[0].read_bytes())
            return dest
        if after:
            return after[0]
        raise FileNotFoundError(f"未找到输出 txt: {output_dir}")
    finally:
        if proc and stop_server:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
