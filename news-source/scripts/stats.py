# -*- coding: utf-8 -*-
"""统计每个事件的信息量：原文篇数/字数/截图/录屏。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = day_dir()
rows = []
for d in sorted(BASE.iterdir()):
    if not d.is_dir() or not d.name[0].isdigit():
        continue
    texts = list((d / "原文").glob("*.md"))
    chars = 0
    for t in texts:
        body = t.read_text(encoding="utf-8", errors="replace").split("---", 1)[-1]
        chars += len(body.strip())
    shots = len(list((d / "截图").glob("*"))) if (d / "截图").exists() else 0
    vids = len(list((d / "录屏").glob("*.mp4"))) if (d / "录屏").exists() else 0
    rows.append((d.name, len(texts), chars, shots, vids))
print(f"{'事件':<24}{'原文':>4}{'正文字数':>8}{'截图':>5}{'录屏':>5}")
tot = [0, 0, 0, 0]
for r in rows:
    print(f"{r[0]:<24}{r[1]:>4}{r[2]:>8}{r[3]:>5}{r[4]:>5}")
    for i in range(4):
        tot[i] += r[i + 1]
print(f"{'合计':<24}{tot[0]:>4}{tot[1]:>8}{tot[2]:>5}{tot[3]:>5}")
