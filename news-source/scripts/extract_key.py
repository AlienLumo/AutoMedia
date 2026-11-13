# -*- coding: utf-8 -*-
"""按关键词抽取关键句，补充细节。"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = day_dir()

TARGETS = {
 "04_gemini4-carbon": ["Gemini 4 Carbon", "Carbon", "TPU", "基准", "多模态"],
 "06_openai-business": ["Businesses in ChatGPT", "profile", "business", "Odessia", "advertis"],
 "02_anthropic-office": ["Whiteboards", "Sheets", "Data", "Microsoft", "office", "Meetings"],
 "07_nvidia-huang": ["Jensen", "Huang", "spy", "China", "免职", "调查"],
 "05_alibaba-qwen-tpu": ["Qwen4", "T-Head", "IPO", "平头哥", "Qwen Code"],
}

for slug, kws in TARGETS.items():
    print(f"\n### {slug}")
    d = BASE / slug
    for f in sorted((d / "原文").glob("*.md"), key=lambda p: -p.stat().st_size)[:4]:
        t = f.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in t.splitlines() if len(l.strip()) > 25]
        picked = []
        for l in lines:
            if any(k.lower() in l.lower() for k in kws):
                picked.append(l)
            if len(picked) >= 4:
                break
        if picked:
            print(f"  [{f.stem}]")
            for p in picked[:4]:
                print("   ·", p[:230])
