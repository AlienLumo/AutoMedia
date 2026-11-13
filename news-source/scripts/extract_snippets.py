# -*- coding: utf-8 -*-
"""从已抓取原文中抽取「事实句」，供写文案素材用（控制输出长度）。"""
import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = day_dir()
KEY = re.compile(r"(亿美元|万亿|亿元|%|％|估值|募资|IPO|发布|融资|营收|参数|榜单|基准|token|亿|万|倍|排名|第一)")

for d in sorted(BASE.iterdir()):
    if not d.is_dir() or not d.name[0].isdigit():
        continue
    files = sorted((d / "原文").glob("*.md"), key=lambda p: -p.stat().st_size)
    print(f"\n### {d.name}")
    shown = 0
    for f in files[:3]:
        t = f.read_text(encoding="utf-8", errors="replace")
        body = t.split("---", 1)[-1]
        paras = [p.strip() for p in body.splitlines() if len(p.strip()) > 20]
        # 首段
        head = next((p for p in paras if len(p) > 40), "")
        if head:
            print(f"  [{f.stem}] 首段: {head[:220]}")
        hits = []
        for p in paras:
            if KEY.search(p) and 20 < len(p) < 260:
                hits.append(p)
            if len(hits) >= 3:
                break
        for h in hits:
            print(f"    · {h[:200]}")
        shown += 1
        if shown >= 2:
            break
