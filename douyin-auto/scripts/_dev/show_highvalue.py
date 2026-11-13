# -*- coding: utf-8 -*-
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

p = SKILL / "config" / "video_search_state.json"
d = json.loads(p.read_text(encoding="utf-8"))
a = d.get("authors") or []

hi = [x for x in a if (x.get("videos_hit") or 0) >= 3 and (x.get("fans") or 0) >= 100000]
hi.sort(key=lambda x: (-(x.get("videos_hit") or 0), -(x.get("fans") or 0)))
hi2 = [x for x in a if (x.get("videos_hit") or 0) >= 2 and (x.get("fans") or 0) >= 100000]

print(f"命中≥3条 且 ≥10万粉: {len(hi)} 个")
print(f"命中≥2条 且 ≥10万粉: {len(hi2)} 个")
print()
for i, x in enumerate(hi[:24], 1):
    themes = ",".join(x.get("themes") or [])[:14]
    print(f'  {i:>2}. {x["fans"]/1e4:>6.0f}万  命中{x["videos_hit"]}条  [{themes}]  {x["nickname"]}')
if len(hi) > 24:
    print(f"  ... 共 {len(hi)} 个")
print()
tot_hi = sum(1 for _ in hi)
print(f"预计耗时（25 视频/博主）：")
for gap, label in [(90, "间隔90s"), (60, "间隔60s"), (45, "间隔45s")]:
    per_vid = (gap * 1.3 + 50) / 60.0   # 间隔(90-1.6x均值≈1.3x) + 工作约50s
    hours = tot_hi * 25 * per_vid / 60.0
    print(f"  {label}: {per_vid:.2f} 分/视频 → {hours:.1f} 小时 ({hours/24:.1f} 天)")
