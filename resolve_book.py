#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse fanqie/changdu share URLs into book_id."""
from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(newurl, code, msg, headers, fp)


def _extract_book_id_from_query(url: str) -> str | None:
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for key in ("book_id", "bookId", "bookid"):
        vals = qs.get(key)
        if vals and re.fullmatch(r"\d{10,}", vals[0]):
            return vals[0]
    m = re.search(r"(?:book_id|bookId)=(\d{10,})", url)
    return m.group(1) if m else None


def resolve_changdu_short(url_or_code: str) -> str:
    text = url_or_code.strip()
    m = re.search(r"changdunovel\.com/t/([A-Za-z0-9_-]+)", text)
    code = m.group(1) if m else text.strip("/").split("/")[-1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,32}", code):
        raise ValueError("bad changdu short link: " + str(url_or_code))

    short = "https://changdunovel.com/t/{}/".format(code)
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(short, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        opener.open(req, timeout=20)
        raise RuntimeError("changdu short link did not redirect: " + short)
    except urllib.error.HTTPError as e:
        loc = e.headers.get("Location") or ""
        if not loc:
            with urllib.request.urlopen(
                urllib.request.Request(short, headers={"User-Agent": UA}), timeout=20
            ) as resp:
                loc = resp.geturl()
        if loc.startswith("/"):
            loc = urllib.parse.urljoin(short, loc)
        book_id = _extract_book_id_from_query(loc)
        if not book_id:
            raise RuntimeError("no book_id in changdu redirect: " + loc)
        return book_id


def resolve_book_id(text: str) -> str:
    raw = text.strip()
    if re.fullmatch(r"\d{15,}", raw):
        return raw

    bid = _extract_book_id_from_query(raw)
    if bid:
        return bid

    m = re.search(r"fanqienovel\.com/page/(\d{15,})", raw)
    if m:
        return m.group(1)

    if "changdunovel.com/t/" in raw:
        return resolve_changdu_short(raw)

    if "changdunovel.com" in raw:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(raw, headers={"User-Agent": UA}), timeout=20
            ) as resp:
                bid = _extract_book_id_from_query(resp.geturl())
                if bid:
                    return bid
        except Exception:
            pass
        if "/t/" in raw:
            return resolve_changdu_short(raw)

    m = re.search(r"(\d{15,})", raw)
    if m:
        return m.group(1)

    raise ValueError("cannot parse book_id: " + text)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    target = sys.argv[1] if len(sys.argv) > 1 else "https://changdunovel.com/t/8ROF4ofKDwc/"
    print(resolve_book_id(target))
