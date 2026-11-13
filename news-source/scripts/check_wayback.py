# -*- coding: utf-8 -*-
"""检查付费墙链接是否有 Wayback Machine 快照。"""
import json, sys, urllib.parse, urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = str(day_dir())
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

import pathlib
rows = []
for d in sorted(pathlib.Path(BASE).iterdir()):
    if not d.is_dir() or not d.name[0].isdigit():
        continue
    lj = d / "links.json"
    if not lj.exists():
        continue
    for m in json.loads(lj.read_text(encoding="utf-8")):
        if m.get("chars", 0) <= 200:
            rows.append((d.name, m["label"], m["url"], m.get("status")))

print(f"{'事件':<22}{'标签':<18}{'状态':<6}{'存档'}")
for slug, label, url, st in rows:
    ok, ts = "-", ""
    try:
        q = "https://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
        req = urllib.request.Request(q, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        snap = data.get("archived_snapshots", {}).get("closest")
        if snap:
            ok, ts = "YES", snap.get("timestamp", "")
        else:
            ok = "NO"
    except Exception as e:
        ok = "ERR"
    print(f"{slug:<22}{label:<18}{str(st):<6}{ok} {ts}")
