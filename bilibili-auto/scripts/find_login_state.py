# -*- coding: utf-8 -*-
"""Locate B站 login state inside the project WITHOUT printing secret values."""
import json
import os
import sqlite3
import sys
from pathlib import Path
from _paths import PROJECT

ROOT = PROJECT
SKIP = {"node_modules", "vendor", ".git", "__pycache__", ".venv", "dist"}
HITS = []

def mask(v):
    if not isinstance(v, str) or not v:
        return "(empty)"
    return f"{v[:4]}...{v[-4:]} len={len(v)}"


def walk():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        depth = len(Path(dirpath).relative_to(ROOT).parts)
        if depth > 5:
            dirnames[:] = []
            continue
        for fn in filenames:
            p = Path(dirpath) / fn
            low = fn.lower()
            if low in ("cookies", "cookies.sqlite", "cookies-journal"):
                HITS.append(("cookiedb", p))
            elif "cookie" in low or "session" in low or "credential" in low:
                HITS.append(("candidate", p))


def inspect(p, kind):
    try:
        size = p.stat().st_size
    except Exception:
        return
    rel = str(p.relative_to(ROOT))
    if size > 8_000_000:
        print(f"  [skip big] {rel} ({size/1e6:.1f}MB)")
        return
    # sqlite cookies db
    if kind == "cookiedb" and p.suffix != ".json":
        try:
            con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
            rows = con.execute(
                "select host_key,name,length(encrypted_value),length(value) "
                "from cookies where name in ('SESSDATA','buvid3','bili_jct',"
                "'DedeUserID','b_nut')").fetchall()
            con.close()
            if rows:
                print(f"  [cookie db] {rel}")
                for h, n, le, lv in rows:
                    print(f"      {n:<12} host={h} encrypted_bytes={le} plain_bytes={lv}")
        except Exception as e:
            print(f"  [cookie db?] {rel} -> {e}")
        return
    if p.suffix.lower() == ".json":
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return
        flat = {}
        def flatd(o, pre=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    if isinstance(v, (dict, list)):
                        flatd(v, pre + k + ".")
                    else:
                        flat[k] = v
            elif isinstance(o, list):
                for i, v in enumerate(o):
                    flatd(v, pre + str(i) + ".")
        flatd(d)
        keys = [k for k in flat if any(s in k for s in
                ("SESSDATA", "buvid3", "bili_jct", "DedeUserID", "session", "token"))]
        if keys:
            print(f"  [json creds] {rel}")
            for k in keys[:8]:
                v = flat[k]
                if any(s in k for s in ("SESSDATA", "bili_jct", "session", "token")):
                    print(f"      {k} = {mask(str(v))}")
                else:
                    print(f"      {k} = {mask(str(v))}")
        return
    # plain text cookie file
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    except Exception:
        return
    if "SESSDATA" in txt:
        print(f"  [text cookie] {rel} ({size}B)")


print(f"扫描根目录: {ROOT}\n")
walk()
print(f"发现 {len(HITS)} 个候选文件\n")
for kind, p in HITS:
    inspect(p, kind)
