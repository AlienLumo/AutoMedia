# -*- coding: utf-8 -*-
"""查看深度采集进度状态。"""
import json
from pathlib import Path
from _paths import PROJECT

PROJ = PROJECT
s = PROJ / "1AMdata" / "_state" / "deep_collect.json"
if not s.exists():
    print("state 文件不存在")
    raise SystemExit
d = json.loads(s.read_text(encoding="utf-8"))
accs = d.get("accounts", {})
print(f"账号状态记录: {len(accs)}")
for mid, a in accs.items():
    print(f"  {a.get('name'):<24} stage={a.get('stage'):<10} "
          f"pool={len(a.get('pool') or []):>3} selected={len(a.get('selected') or []):>3} "
          f"done={len(a.get('done') or []):>3} 评论={a.get('total_cm', 0):>5} "
          f"字幕={a.get('total_sub', 0):>3}")
