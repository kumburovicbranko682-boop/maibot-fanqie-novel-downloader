#!/usr/bin/env python3
"""Build Tomato engine from vendored source into bin/."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "third_party" / "Tomato-Novel-Downloader"
BIN = ROOT / "bin"
CARGO_NO = SRC / "Cargo_no_official.toml"
CARGO = SRC / "Cargo.toml"
CARGO_BAK = SRC / "Cargo.toml.official.bak"


def main() -> int:
    if not SRC.is_dir():
        print("missing source:", SRC, file=sys.stderr)
        return 1
    if shutil.which("cargo") is None:
        print("cargo not found: https://rustup.rs/", file=sys.stderr)
        return 1

    restored = False
    if CARGO_NO.is_file():
        if CARGO.is_file() and not CARGO_BAK.is_file():
            shutil.copy2(CARGO, CARGO_BAK)
        shutil.copy2(CARGO_NO, CARGO)
        restored = True
        print("switched to Cargo_no_official.toml")

    cmd = [
        "cargo",
        "build",
        "--release",
        "--no-default-features",
        "--features",
        "no-official-api,tts,clipboard,clipboard-arboard",
    ]
    print("+", " ".join(cmd), "(cwd=%s)" % SRC)
    try:
        result = subprocess.run(cmd, cwd=SRC, check=False)
    finally:
        if restored and CARGO_BAK.is_file():
            shutil.move(str(CARGO_BAK), str(CARGO))
            print("restored Cargo.toml")

    if result.returncode != 0:
        return int(result.returncode)

    name = "tomato-novel-downloader.exe" if os.name == "nt" else "tomato-novel-downloader"
    built = SRC / "target" / "release" / name
    if not built.is_file():
        alt = SRC / "target" / "release" / "tomato-novel-downloader"
        if alt.is_file():
            built = alt
            name = alt.name
        else:
            print("artifact missing:", built, file=sys.stderr)
            return 1

    BIN.mkdir(parents=True, exist_ok=True)
    dest = BIN / name
    shutil.copy2(built, dest)
    print("copied to", dest, dest.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
