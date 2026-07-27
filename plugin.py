"""Fanqie / Changdu novel downloader MaiBot plugin."""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

try:
    from maibot_sdk import Command, MaiBotPlugin
except ImportError:

    def Command(name: str, description: str = "", pattern: str = "", timeout_ms: int = 0):  # type: ignore[misc]
        def _decorator(func):
            func._command_info = {
                "name": name,
                "description": description,
                "pattern": pattern,
                "timeout_ms": timeout_ms,
            }
            return func

        return _decorator

    class MaiBotPlugin:  # type: ignore[no-redef]
        config_model = None

        def __init__(self) -> None:
            self.ctx = None
            if self.config_model is not None:
                self.config = self.config_model()

        def get_components(self) -> list[dict[str, Any]]:
            components: list[dict[str, Any]] = []
            for attr_name in dir(self):
                attr = getattr(self, attr_name, None)
                info = getattr(attr, "_command_info", None)
                if not isinstance(info, dict):
                    continue
                components.append(
                    {
                        "name": info.get("name", attr_name),
                        "type": "command",
                        "metadata": {
                            "command_pattern": info.get("pattern", ""),
                            "description": info.get("description", ""),
                            "handler_name": attr_name,
                            "timeout_ms": info.get("timeout_ms", 0),
                        },
                    }
                )
            return components


from .config import FanqieNovelDownloaderConfig
from .downloader import download_book
from .book_card import build_book_card
from .resolve_book import resolve_book_id

PLUGIN_DIR = Path(__file__).resolve().parent
JOBS_DIR = PLUGIN_DIR / "data" / "jobs"
_DOWNLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fanqie-dl")

# Chinese command tokens via unicode escapes (ASCII source)
XS = "\u5c0f\u8bf4"  # novel
FQ = "\u756a\u8304"  # fanqie
CMD_HELP = "\u5e2e\u52a9"
CMD_DL = "\u4e0b\u8f7d"
CMD_STATUS = "\u72b6\u6001"
CMD_LIST = "\u5217\u8868"
CMD_HISTORY = "\u5386\u53f2"
CMD_INFO = "\u4fe1\u606f"

COMMAND_PATTERN = (
    rf"^(?:#{XS}|#{FQ}|#fanqie|#novel)"
    r"(?:\s+(?P<args>[\s\S]*))?\s*$"
)


def normalize_token(value: Any) -> str:
    return str(value or "").strip().lower()


class FanqieNovelDownloaderPlugin(MaiBotPlugin):
    """Local signer gateway novel downloader plugin."""

    config_model = FanqieNovelDownloaderConfig

    def __init__(self) -> None:
        super().__init__()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._jobs_lock = asyncio.Lock()
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    async def on_load(self) -> None:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        (PLUGIN_DIR / "data" / "output").mkdir(parents=True, exist_ok=True)
        (PLUGIN_DIR / "data" / "tomato-data").mkdir(parents=True, exist_ok=True)
        self._load_jobs()
        if getattr(self, "ctx", None) is not None and hasattr(self.ctx, "logger"):
            self.ctx.logger.info(f"{FQ}{XS}\u4e0b\u8f7d\u63d2\u4ef6\u5df2\u52a0\u8f7d")

    async def on_unload(self) -> None:
        for task in list(self._bg_tasks):
            task.cancel()
        self._bg_tasks.clear()
        if getattr(self, "ctx", None) is not None and hasattr(self.ctx, "logger"):
            self.ctx.logger.info(f"{FQ}{XS}\u4e0b\u8f7d\u63d2\u4ef6\u5df2\u5378\u8f7d")

    async def on_config_update(
        self, scope: str, config_data: dict[str, object], version: str
    ) -> None:
        del config_data, version
        if scope == "self" and getattr(self, "ctx", None) is not None and hasattr(
            self.ctx, "logger"
        ):
            self.ctx.logger.info(f"{FQ}{XS}\u4e0b\u8f7d\u63d2\u4ef6\u914d\u7f6e\u5df2\u66f4\u65b0")

    @Command(
        "fanqie_novel_download",
        description="Download Fanqie/Changdu novel as TXT via local signer gateway",
        pattern=COMMAND_PATTERN,
        timeout_ms=30000,
    )
    async def handle_novel_command(
        self,
        stream_id: str = "",
        group_id: str = "",
        platform: str = "",
        user_id: str = "",
        matched_groups: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[bool, str, bool]:
        del group_id
        if not getattr(self.config.plugin, "enabled", True):
            return await self._reply(
                stream_id, False, f"{FQ}{XS}\u4e0b\u8f7d\u63d2\u4ef6\u5f53\u524d\u5df2\u5173\u95ed\u3002"
            )

        args = self._extract_arguments(matched_groups, kwargs)
        action, _, payload = args.partition(" ")
        action = normalize_token(action)
        payload = payload.strip()
        administrator = await self._is_administrator(platform, user_id)

        if not action or action in {CMD_HELP, "help", "?"}:
            return await self._reply(stream_id, True, self._help_text())

        if action in {CMD_STATUS, "status"}:
            return await self._reply(stream_id, True, self._status_text(payload))

        if action in {CMD_LIST, "list", CMD_HISTORY}:
            return await self._reply(stream_id, True, self._list_text())

        if action in {CMD_INFO, "info", "card", "\u8be6\u60c5"}:
            if not payload:
                return await self._reply(
                    stream_id,
                    False,
                    f"\u7528\u6cd5\uff1a#{XS} {CMD_INFO} <\u94fe\u63a5|book_id>",
                )
            return await self._send_book_card_only(stream_id, payload)

        if action in {CMD_DL, "download", "dl", "get"}:
            if not self.config.security.allow_public and not administrator:
                return await self._reply(
                    stream_id, False, "\u4f60\u6ca1\u6709\u6743\u9650\u53d1\u8d77\u4e0b\u8f7d\u3002"
                )
            if not payload:
                return await self._reply(
                    stream_id,
                    False,
                    f"\u7528\u6cd5\uff1a#{XS} {CMD_DL} <{FQ}\u94fe\u63a5|\u5e38\u8bfb\u77ed\u94fe|book_id>",
                )
            return await self._start_download(
                stream_id=stream_id,
                platform=platform,
                user_id=user_id,
                target=payload,
            )

        if args and ("http" in args or re.fullmatch(r"\d{10,}", args)):
            if not self.config.security.allow_public and not administrator:
                return await self._reply(
                    stream_id, False, "\u4f60\u6ca1\u6709\u6743\u9650\u53d1\u8d77\u4e0b\u8f7d\u3002"
                )
            return await self._start_download(
                stream_id=stream_id,
                platform=platform,
                user_id=user_id,
                target=args,
            )

        return await self._reply(
            stream_id,
            False,
            f"\u672a\u77e5\u5b50\u547d\u4ee4\u3002\u53d1\u9001 #{XS} {CMD_HELP} \u67e5\u770b\u7528\u6cd5\u3002",
        )

    async def _start_download(
        self,
        *,
        stream_id: str,
        platform: str,
        user_id: str,
        target: str,
    ) -> tuple[bool, str, bool]:
        try:
            book_id = await asyncio.to_thread(resolve_book_id, target)
        except Exception as exc:  # noqa: BLE001
            return await self._reply(
                stream_id, False, f"\u65e0\u6cd5\u89e3\u6790\u4e66\u7c4d\uff1a{exc}"
            )

        job_id = uuid.uuid4().hex[:8]
        job = {
            "id": job_id,
            "book_id": book_id,
            "target": target,
            "state": "queued",
            "title": "",
            "saved": 0,
            "total": 0,
            "path": "",
            "error": "",
            "stream_id": stream_id,
            "platform": platform,
            "user_id": user_id,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        async with self._jobs_lock:
            self._jobs[job_id] = job
            self._persist_jobs()

        card_text = ""
        try:
            card = await asyncio.to_thread(build_book_card, book_id, target=target)
            job["title"] = card.get("title") or job.get("title") or ""
            job["author"] = card.get("author") or ""
            if isinstance(card.get("chapters"), int):
                job["total"] = card["chapters"]
            self._persist_jobs()
            card_text = str(card.get("text") or "")
            cover_b64 = card.get("cover_base64")
            if card_text and cover_b64:
                await self._send_text_image(card_text, str(cover_b64), stream_id)
            elif card_text:
                await self._safe_send_text(stream_id, card_text)
        except Exception as exc:  # noqa: BLE001
            self._log_warning(f"book card failed: {exc}")

        notice = (
            f"\u5df2\u5f00\u59cb\u4e0b\u8f7d\uff0c\u4efb\u52a1 {job_id}\n"
            f"\u53ef\u7528 #{XS} {CMD_STATUS} {job_id} \u67e5\u770b\u8fdb\u5ea6\u3002"
        )
        await self._safe_send_text(stream_id, notice)

        task = asyncio.create_task(
            self._run_download_job(job_id), name=f"fanqie-job-{job_id}"
        )
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return True, card_text or notice, True

    async def _run_download_job(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job:
            return
        stream_id = str(job.get("stream_id") or "")
        cfg = self.config.downloader
        loop = asyncio.get_running_loop()
        last_notice = 0.0

        def on_progress(info: dict[str, Any]) -> None:
            nonlocal last_notice
            job["state"] = str(info.get("state") or job.get("state") or "running")
            if info.get("title"):
                job["title"] = str(info["title"])
            if info.get("saved") is not None:
                job["saved"] = info.get("saved") or 0
            if info.get("total") is not None:
                job["total"] = info.get("total") or 0
            job["updated_at"] = time.time()
            now = time.time()
            if stream_id and now - last_notice >= 45:
                last_notice = now
                title = job.get("title") or job.get("book_id")
                msg = (
                    f"\u4e0b\u8f7d\u8fdb\u5ea6 `{job_id}`\n"
                    f"\u300a{title}\u300b {job.get('saved')}/{job.get('total') or '?'}"
                )
                asyncio.run_coroutine_threadsafe(
                    self._safe_send_text(stream_id, msg), loop
                )

        try:
            job["state"] = "running"
            job["updated_at"] = time.time()
            self._persist_jobs()
            path: Path = await loop.run_in_executor(
                _DOWNLOAD_EXECUTOR,
                lambda: download_book(
                    str(job["book_id"]),
                    exe=Path(cfg.tomato_exe),
                    data_dir=Path(cfg.tomato_data_dir),
                    output_dir=Path(cfg.output_dir),
                    addr=cfg.gateway_addr,
                    password=cfg.gateway_password,
                    workers=int(cfg.max_workers),
                    progress=on_progress,
                    stop_server=True,
                ),
            )
            job["state"] = "done"
            job["path"] = str(path)
            job["title"] = job.get("title") or path.stem
            job["updated_at"] = time.time()
            self._persist_jobs()
            size_mb = path.stat().st_size / (1024 * 1024)
            done_text = (
                f"\u4e0b\u8f7d\u5b8c\u6210 `{job_id}`\n"
                f"\u300a{job['title']}\u300b\n"
                f"\u6587\u4ef6\uff1a{path.name}\uff08{size_mb:.2f} MB\uff09\n"
                f"\u8def\u5f84\uff1a{path}"
            )
            await self._safe_send_text(stream_id, done_text)
            if cfg.try_send_file:
                await self._try_send_file(stream_id, path)
        except Exception as exc:  # noqa: BLE001
            job["state"] = "failed"
            job["error"] = str(exc)
            job["updated_at"] = time.time()
            self._persist_jobs()
            await self._safe_send_text(
                stream_id, f"\u4e0b\u8f7d\u5931\u8d25 `{job_id}`\n{exc}"
            )


    async def _send_book_card_only(self, stream_id: str, target: str) -> tuple[bool, str, bool]:
        try:
            book_id = await asyncio.to_thread(resolve_book_id, target)
        except Exception as exc:  # noqa: BLE001
            return await self._reply(
                stream_id, False, f"\u65e0\u6cd5\u89e3\u6790\u4e66\u7c4d\uff1a{exc}"
            )
        try:
            card = await asyncio.to_thread(build_book_card, book_id, target=target)
        except Exception as exc:  # noqa: BLE001
            return await self._reply(stream_id, False, f"\u83b7\u53d6\u4e66\u7c4d\u4fe1\u606f\u5931\u8d25\uff1a{exc}")
        text = str(card.get("text") or "")
        cover_b64 = card.get("cover_base64")
        if text and cover_b64:
            ok = await self._send_text_image(text, str(cover_b64), stream_id)
            return bool(ok), text, True
        if text:
            return await self._reply(stream_id, True, text)
        return await self._reply(stream_id, False, "\u672a\u83b7\u53d6\u5230\u4e66\u7c4d\u4fe1\u606f\u3002")

    async def _send_text_image(self, text: str, image_base64: str, stream_id: str) -> bool:
        if not stream_id or getattr(self, "ctx", None) is None:
            return False
        send = getattr(self.ctx, "send", None)
        if send is None:
            return False
        hybrid = getattr(send, "hybrid", None)
        if callable(hybrid):
            try:
                sent = await hybrid(
                    [
                        {"type": "text", "content": text},
                        {"type": "image", "content": image_base64},
                    ],
                    stream_id,
                )
                if sent is not False:
                    return True
            except Exception as exc:  # noqa: BLE001
                self._log_warning(f"hybrid send failed: {exc}")
        try:
            text_sent = await self.ctx.send.text(text, stream_id)
            image_fn = getattr(send, "image", None)
            if not callable(image_fn):
                return text_sent is not False
            image_sent = await image_fn(image_base64, stream_id)
            return text_sent is not False and image_sent is not False
        except Exception as exc:  # noqa: BLE001
            self._log_warning(f"text+image send failed: {exc}")
            try:
                await self.ctx.send.text(text, stream_id)
            except Exception:
                pass
            return False

    async def _try_send_file(self, stream_id: str, path: Path) -> None:
        if not stream_id or getattr(self, "ctx", None) is None:
            return
        send = getattr(self.ctx, "send", None)
        if send is None:
            return
        custom = getattr(send, "custom", None)
        if not callable(custom):
            return
        payloads = [
            {"type": "file", "path": str(path), "name": path.name},
            {"type": "file", "file": str(path), "name": path.name},
            {"file": str(path), "name": path.name},
        ]
        for payload in payloads:
            try:
                result = await custom(payload, stream_id)
                if result is not False:
                    return
            except Exception as exc:  # noqa: BLE001
                self._log_warning(f"send.custom file failed: {exc}")

    async def _safe_send_text(self, stream_id: str, text: str) -> None:
        if not stream_id or getattr(self, "ctx", None) is None:
            return
        try:
            await self.ctx.send.text(text, stream_id)
        except Exception as exc:  # noqa: BLE001
            self._log_warning(f"send text failed: {exc}")

    def _status_text(self, job_id: str = "") -> str:
        job_id = job_id.strip()
        if job_id:
            job = self._jobs.get(job_id)
            if not job:
                return f"\u672a\u627e\u5230\u4efb\u52a1 `{job_id}`\u3002"
            return self._format_job(job)
        running = [
            j
            for j in self._jobs.values()
            if j.get("state") in {"queued", "running"}
        ]
        if not running:
            return (
                f"\u5f53\u524d\u6ca1\u6709\u8fdb\u884c\u4e2d\u7684\u4e0b\u8f7d\u4efb\u52a1\u3002"
                f"\u53ef\u7528 `#{XS} {CMD_LIST}` \u67e5\u770b\u5386\u53f2\u3002"
            )
        lines = ["\u8fdb\u884c\u4e2d\u7684\u4efb\u52a1\uff1a"]
        for job in sorted(running, key=lambda x: x.get("created_at", 0), reverse=True):
            lines.append(self._format_job(job))
            lines.append("\u2500" * 12)
        return "\n".join(lines).rstrip("\u2500\n ")

    def _list_text(self) -> str:
        if not self._jobs:
            return "\u8fd8\u6ca1\u6709\u4e0b\u8f7d\u8bb0\u5f55\u3002"
        items = sorted(
            self._jobs.values(), key=lambda x: x.get("created_at", 0), reverse=True
        )[:15]
        lines = [f"\u6700\u8fd1 {len(items)} \u6761\u4efb\u52a1\uff1a"]
        for job in items:
            title = job.get("title") or job.get("book_id")
            lines.append(
                f"- `{job.get('id')}` [{job.get('state')}] \u300a{title}\u300b "
                f"{job.get('saved')}/{job.get('total') or '?'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_job(job: dict[str, Any]) -> str:
        title = job.get("title") or "(\u89e3\u6790\u4e2d)"
        lines = [
            f"\u4efb\u52a1 `{job.get('id')}`",
            f"\u72b6\u6001\uff1a{job.get('state')}",
            f"\u4e66\u540d\uff1a{title}",
            f"book_id\uff1a{job.get('book_id')}",
            f"\u8fdb\u5ea6\uff1a{job.get('saved')}/{job.get('total') or '?'}",
        ]
        if job.get("path"):
            lines.append(f"\u6587\u4ef6\uff1a{job['path']}")
        if job.get("error"):
            lines.append(f"\u9519\u8bef\uff1a{job['error']}")
        return "\n".join(lines)

    async def _is_administrator(self, platform: str, user_id: str) -> bool:
        normalized_user = normalize_token(user_id)
        normalized_platform = normalize_token(platform)
        if not normalized_user:
            return False
        candidates = {normalized_user, f"{normalized_platform}:{normalized_user}"}
        administrators = {
            normalize_token(item)
            for item in self.config.security.administrators
            if normalize_token(item)
        }
        if candidates & administrators:
            return True
        if not self.config.security.inherit_plugin_management_permissions:
            return False
        try:
            inherited = await self.ctx.config.get("plugin.permission", [])
        except Exception:
            inherited = []
        inherited = inherited if isinstance(inherited, list) else []
        return bool(
            candidates
            & {normalize_token(item) for item in inherited if normalize_token(item)}
        )

    async def _reply(
        self, stream_id: str, success: bool, text: str
    ) -> tuple[bool, str, bool]:
        if stream_id:
            await self.ctx.send.text(text, stream_id)
        return success, text, True

    def _load_jobs(self) -> None:
        path = JOBS_DIR / "jobs.json"
        if not path.exists():
            self._jobs = {}
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data.get("items") if isinstance(data, dict) else data
            if isinstance(items, list):
                self._jobs = {
                    str(item["id"]): item
                    for item in items
                    if isinstance(item, dict) and item.get("id")
                }
            elif isinstance(items, dict):
                self._jobs = {str(k): v for k, v in items.items() if isinstance(v, dict)}
            else:
                self._jobs = {}
        except Exception:
            self._jobs = {}

    def _persist_jobs(self) -> None:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        path = JOBS_DIR / "jobs.json"
        payload = {
            "items": sorted(
                self._jobs.values(),
                key=lambda x: x.get("created_at", 0),
                reverse=True,
            )[:50]
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(path)

    def _log_warning(self, message: str) -> None:
        if getattr(self, "ctx", None) is not None and hasattr(self.ctx, "logger"):
            self.ctx.logger.warning(message)

    @staticmethod
    def _extract_arguments(
        matched_groups: dict[str, Any] | None, kwargs: dict[str, Any]
    ) -> str:
        if isinstance(matched_groups, dict) and isinstance(
            matched_groups.get("args"), str
        ):
            return str(matched_groups["args"]).strip()
        raw_text = str(kwargs.get("text") or "").strip()
        return re.sub(
            rf"^(?:#{XS}|#{FQ}|#fanqie|#novel)\s*",
            "",
            raw_text,
            flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _help_text() -> str:
        return (
            f"{FQ}{XS}\u4e0b\u8f7d\n"
            f"#{XS} {CMD_HELP}\n"
            f"#{XS} {CMD_DL} <{FQ}\u94fe\u63a5|\u5e38\u8bfb\u77ed\u94fe|book_id>\n"
            f"#{XS} <\u94fe\u63a5>          \uff08\u7b80\u5199\uff09\n"
            f"#{XS} {CMD_INFO} <\u94fe\u63a5|book_id>\n"
            f"#{XS} {CMD_STATUS} [\u4efb\u52a1ID]\n"
            f"#{XS} {CMD_LIST}\n\n"
            f"\u540c\u4e49\u524d\u7f00\uff1a#{FQ} / #fanqie / #novel\n\n"
            "\u8bf4\u660e\uff1a\n"
            "- \u672c\u673a\u7b7e\u540d\u7f51\u5173\u76f4\u8fde\u5b98\u65b9 API\uff0c"
            "\u4e0d\u4f9d\u8d56\u7b2c\u4e09\u65b9 content \u955c\u50cf\n"
            "- \u4e0b\u8f7d\u5728\u540e\u53f0\u6267\u884c\uff0c\u5b8c\u6210\u540e\u56de\u4f20\u672c\u5730 TXT \u8def\u5f84\n"
            "- \u82e5\u9002\u914d\u5668\u652f\u6301\u6587\u4ef6\u6d88\u606f\uff0c\u4f1a\u5c1d\u8bd5\u76f4\u63a5\u53d1\u9001 TXT\n"
        )


def create_plugin() -> FanqieNovelDownloaderPlugin:
    """Create plugin instance."""
    return FanqieNovelDownloaderPlugin()
