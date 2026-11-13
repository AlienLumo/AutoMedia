# -*- coding: utf-8 -*-
"""清理误分类产生的重复截图：英文站点不应有 CN_ 前缀（同名 EN_ 存在时删除 CN_）。"""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = day_dir()
EN_LABELS = ("cnbc", "deadline", "verge", "toms", "techcrunch", "openai", "investing",
             "bloomberg", "nytimes", "marketwatch", "wired", "theinformation", "variety",
             "latent", "wapo", "washingtonpost")
removed = 0
for d in sorted(BASE.iterdir()):
    if not d.is_dir() or not d.name[0].isdigit():
        continue
    for sub in ("截图", "录屏"):
        p = d / sub
        if not p.exists():
            continue
        for f in list(p.glob("CN_*")):
            label = f.name[3:].split("_")[0]
            if any(label.startswith(e) for e in EN_LABELS):
                if any(p.glob("EN_" + label + "*")):
                    f.unlink()
                    removed += 1
print("removed", removed)
