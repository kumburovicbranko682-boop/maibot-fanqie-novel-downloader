"""Fetch novel card metadata and cover image."""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Referer": "https://fanqienovel.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _json_unescape(value: str) -> str:
    try:
        return json.loads('"' + value + '"')
    except Exception:
        return (
            value.replace(r"\u002F", "/")
            .replace(r"\/", "/")
            .replace(r"\n", "\n")
            .replace(r"\"", '"')
        )


def _json_str_field(html: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}":"(.*?)"', html)
    if not m:
        return None
    text = _json_unescape(m.group(1)).strip()
    return text or None


def _json_int_field(html: str, key: str) -> int | None:
    m = re.search(rf'"{re.escape(key)}":\s*(\d+)', html)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _cover_from_thumb_uri(thumb_uri: str) -> str:
    uri = thumb_uri.lstrip("/")
    if uri.startswith("http"):
        return uri
    return f"https://p3-novel.byteimg.com/{uri}~tplv-resize:600:800.image"


def _normalize_cover_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if "~tplv-resize:225:300.image" in url:
        url = url.replace("~tplv-resize:225:300.image", "~tplv-resize:600:800.image")
    return url


def _parse_initial_state(html: str) -> dict[str, Any] | None:
    marker = "window.__INITIAL_STATE__="
    idx = html.find(marker)
    if idx < 0:
        marker = "window.__INITIAL_STATE__ ="
        idx = html.find(marker)
        if idx < 0:
            return None
    start = idx + len(marker)
    while start < len(html) and html[start].isspace():
        start += 1
    try:
        obj, _end = json.JSONDecoder().raw_decode(html, start)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _info_from_page_obj(page: dict[str, Any], book_id: str) -> dict[str, Any]:
    bid = str(page.get("bookId") or page.get("book_id") or "")
    if bid and bid != str(book_id):
        return {}
    title = str(page.get("bookName") or page.get("book_name") or "").strip()
    author = str(page.get("authorName") or page.get("author") or "").strip()
    cover = _normalize_cover_url(
        str(page.get("thumbUrl") or page.get("thumbUri") or page.get("thumb_url") or "")
        or None
    )
    chapters = page.get("chapterTotal")
    if chapters is None:
        chapters = page.get("serialCount") or page.get("serial_count")
    if chapters is None and isinstance(page.get("itemIds"), list):
        chapters = len(page["itemIds"])
    try:
        chapters_i = int(chapters) if chapters not in (None, "") else None
    except Exception:
        chapters_i = None
    if chapters_i is not None and chapters_i <= 0:
        chapters_i = None
    return {
        "book_id": book_id,
        "title": title,
        "author": author,
        "chapters": chapters_i,
        "cover_url": cover,
        "source": "initial_state",
    }


def _info_from_fallbacks(html: str, book_id: str) -> dict[str, Any]:
    title = ""
    author = ""
    cover = None

    m = re.search(
        r'<script[^>]+type="application/ld\+json"[^>]*>(\{.*?\})</script>',
        html,
        re.I | re.S,
    )
    if m:
        try:
            obj = json.loads(m.group(1))
            headline = str(obj.get("headline") or "")
            # "书名_书名小说_番茄小说官网" → 书名
            title = headline.split("_")[0].strip() or title
            authors = obj.get("author")
            if isinstance(authors, list) and authors:
                author = str(authors[0].get("name") or "").strip()
            elif isinstance(authors, dict):
                author = str(authors.get("name") or "").strip()
        except Exception:
            pass

    if not title:
        m = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
        if m:
            raw = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            title = raw.split("_")[0].strip()

    if not title:
        m = re.search(
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if m:
            title = m.group(1).split("_")[0].strip()

    if not cover:
        m = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if m:
            cover = _normalize_cover_url(m.group(1))

    return {
        "book_id": book_id,
        "title": title,
        "author": author,
        "chapters": None,
        "cover_url": cover,
        "source": "html_fallback",
    }


def scrape_fanqie_page(book_id: str) -> dict[str, Any]:
    html = _http_get(f"https://fanqienovel.com/page/{book_id}").decode("utf-8", "replace")
    info: dict[str, Any] = {
        "book_id": book_id,
        "title": "",
        "author": "",
        "chapters": None,
        "cover_url": None,
        "source": "fanqienovel_page",
    }

    state = _parse_initial_state(html)
    if isinstance(state, dict):
        page = state.get("page")
        if isinstance(page, dict):
            parsed = _info_from_page_obj(page, book_id)
            for key, value in parsed.items():
                if value:
                    info[key] = value

    if not info.get("title"):
        title = _json_str_field(html, "bookName")
        if title:
            info["title"] = title
    if not info.get("author"):
        author = _json_str_field(html, "authorName") or _json_str_field(html, "author")
        if author:
            info["author"] = author
    if not info.get("cover_url"):
        cover = _normalize_cover_url(
            _json_str_field(html, "thumbUrl") or _json_str_field(html, "thumbUri")
        )
        if cover:
            info["cover_url"] = cover
    if not info.get("chapters"):
        chapters = _json_int_field(html, "chapterTotal") or _json_int_field(
            html, "serialCount"
        )
        if not chapters:
            n = len(set(re.findall(r'"itemId":"(\d+)"', html)))
            chapters = n or None
        if chapters:
            info["chapters"] = chapters

    if not info.get("cover_url"):
        m = re.search(r'class="book-cover-img[^"]*"[^>]*src="([^"]+)"', html)
        if m:
            info["cover_url"] = _normalize_cover_url(m.group(1))

    if not info.get("title") or not info.get("author"):
        fb = _info_from_fallbacks(html, book_id)
        for key in ("title", "author", "cover_url"):
            if not info.get(key) and fb.get(key):
                info[key] = fb[key]

    return info


def scrape_fanqie_page_retry(
    book_id: str, *, attempts: int = 3, delay: float = 0.8
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for i in range(max(1, attempts)):
        try:
            info = scrape_fanqie_page(book_id)
            if info.get("title"):
                return info
            last_exc = RuntimeError("empty title from fanqie page")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        if i + 1 < attempts:
            time.sleep(delay * (i + 1))
    if last_exc:
        raise last_exc
    return {
        "book_id": book_id,
        "title": "",
        "author": "",
        "chapters": None,
        "cover_url": None,
        "source": "empty",
    }


def enrich_via_tomato_search(gw: Any, book_id: str, title_hint: str = "") -> dict[str, Any]:
    queries: list[str] = []
    if title_hint:
        queries.append(title_hint[:40])
        queries.append(title_hint)
    queries.append(book_id)
    seen: set[str] = set()
    for q in queries:
        if not q or q in seen:
            continue
        seen.add(q)
        try:
            data = gw.call(
                "GET", "/api/search?q=" + urllib.parse.quote(q), timeout=30
            )
        except Exception:
            continue
        items = (data or {}).get("items") if isinstance(data, dict) else []
        for item in items or []:
            if str(item.get("book_id") or "") != str(book_id):
                continue
            raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
            thumb_uri = str(raw.get("thumb_uri") or "")
            cover = None
            if thumb_uri:
                cover = _cover_from_thumb_uri(thumb_uri)
            else:
                for key in ("thumb_url", "detail_page_thumb_url", "expand_thumb_url"):
                    if raw.get(key):
                        cover = _normalize_cover_url(str(raw.get(key)))
                        break
            serial = raw.get("serial_count")
            try:
                chapters = int(serial) if serial not in (None, "") else None
            except Exception:
                chapters = None
            return {
                "book_id": book_id,
                "title": str(item.get("title") or raw.get("book_name") or title_hint or ""),
                "author": str(item.get("author") or raw.get("author") or ""),
                "chapters": chapters,
                "cover_url": cover,
                "source": "tomato_search",
            }
    return {}


def download_cover_base64(cover_url: str, max_bytes: int = 2_500_000) -> str | None:
    data: bytes | None = None
    try:
        data = _http_get(cover_url, timeout=20)
    except Exception:
        data = None
    if not data or data[:3] != b"\xff\xd8\xff":
        m = re.search(r"(novel-pic/[a-zA-Z0-9]+)", cover_url or "")
        if m:
            try:
                data = _http_get(_cover_from_thumb_uri(m.group(1)), timeout=20)
            except Exception:
                data = None
    if not data or len(data) > max_bytes:
        return None
    if data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n":
        return base64.b64encode(data).decode("ascii")
    return None


def detect_platform_label(target: str) -> str:
    t = (target or "").lower()
    if "changdunovel" in t:
        return "\u5e38\u8bfb\u5c0f\u8bf4"
    return "\u756a\u8304\u5c0f\u8bf4"


def format_book_card_text(
    *,
    title: str,
    author: str,
    chapters: int | None,
    platform: str,
) -> str:
    title = title or "\u672a\u77e5\u4e66\u540d"
    author = author or "\u672a\u77e5"
    if chapters:
        chapter_line = f"\U0001f4da \u5171 {chapters} \u7ae0"
    else:
        chapter_line = "\U0001f4da \u7ae0\u8282\u6570\u672a\u77e5"
    return (
        f"\U0001f4d6 \u300a{title}\u300b\n"
        f"\u270d\ufe0f \u4f5c\u8005\uff1a{author}\n"
        f"{chapter_line}\n"
        f"\U0001f516 \u5e73\u53f0\uff1a{platform}"
    )


def build_book_card(
    book_id: str,
    *,
    target: str = "",
    gateway: Any | None = None,
) -> dict[str, Any]:
    """Return card dict with text + optional cover_base64."""
    platform = detect_platform_label(target)
    info: dict[str, Any] = {
        "book_id": book_id,
        "title": "",
        "author": "",
        "chapters": None,
        "cover_url": None,
    }
    scrape_error: str | None = None
    try:
        scraped = scrape_fanqie_page_retry(book_id, attempts=3)
        for key, value in scraped.items():
            if value:
                info[key] = value
    except Exception as exc:  # noqa: BLE001
        scrape_error = str(exc)

    if gateway is not None and (
        not info.get("cover_url") or not info.get("title") or not info.get("chapters")
    ):
        try:
            extra = enrich_via_tomato_search(
                gateway, book_id, title_hint=str(info.get("title") or "")
            )
            for key in ("title", "author", "chapters", "cover_url"):
                if not info.get(key) and extra.get(key):
                    info[key] = extra[key]
        except Exception:
            pass

    cover_b64 = None
    if info.get("cover_url"):
        try:
            cover_b64 = download_cover_base64(str(info["cover_url"]))
        except Exception:
            cover_b64 = None

    chapters = info.get("chapters")
    text = format_book_card_text(
        title=str(info.get("title") or ""),
        author=str(info.get("author") or ""),
        chapters=chapters if isinstance(chapters, int) else None,
        platform=platform,
    )
    return {
        "book_id": book_id,
        "title": info.get("title") or "",
        "author": info.get("author") or "",
        "chapters": chapters,
        "platform": platform,
        "cover_url": info.get("cover_url"),
        "cover_base64": cover_b64,
        "text": text,
        "ok": bool(info.get("title")),
        "error": scrape_error,
    }
