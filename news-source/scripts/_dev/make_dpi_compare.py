# -*- coding: utf-8 -*-
"""生成 dsf1 vs dsf2 清晰度对比图；重试 Wayback id_ 抓取。"""
import io, sys, urllib.request
from PIL import Image
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

D = day_dir() / "01_anthropic-ipo" / "截图"
a = Image.open(D / "清晰度对比_dsf1.png")
b = Image.open(D / "清晰度对比_dsf2.png")
# 取标题区域：dsf1 (0,120)-(760,360)  dsf2 同区域 2 倍
box = (0, 120, 760, 360)
ca = a.crop(box).resize((760 * 2, 240 * 2), Image.LANCZOS)   # 1x 放大 → 模糊
cb = b.crop(tuple(v * 2 for v in box))                        # 2x 原生 → 清晰
canvas = Image.new("RGB", (760 * 2, 240 * 2 * 2 + 40), "white")
canvas.paste(ca, (0, 0))
canvas.paste(cb, (0, 240 * 2 + 40))
canvas.save(D / "清晰度对比_拼图.png")
print("compare saved", canvas.size)

url = "https://web.archive.org/web/20261110232754id_/https://www.nytimes.com/2026/11/10/technology/anthropic-ipo-google-amazon.html"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126 Safari/537.36"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read().decode("utf-8", "ignore")
    print("wayback ok", len(raw))
except Exception as e:
    print("wayback fail", e)
