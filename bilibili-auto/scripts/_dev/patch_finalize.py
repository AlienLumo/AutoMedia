# -*- coding: utf-8 -*-
"""修 finalize_roster_v2：额外机构名过滤 + 修正耗时公式。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "finalize_roster_v2.py"
t = f.read_text(encoding="utf-8")

if "EXTRA_INST" not in t:
    t = t.replace(
        'prog = json.loads(PROG.read_text(encoding="utf-8"))',
        'EXTRA_INST = ["联合国", "NASA", "哔哩哔哩", "弹幕网", "欧盟", "世卫",\n'
        '              "教科文", "红十字会", "中科院", "中国航天", "国家航天",\n'
        '              "航天局", "气象局", "地震局", "博物馆", "美术馆", "图书馆",\n'
        '              "档案馆", "国资委", "税务局", "统计局"]\n\n'
        'prog = json.loads(PROG.read_text(encoding="utf-8"))', 1)

if "_bad_inst" not in t:
    t = t.replace(
        "picked = ok + mid",
        'def _bad_inst(name):\n'
        '    return any(w in (name or "") for w in EXTRA_INST)\n\n'
        'ok = [r for r in ok if not _bad_inst(r.get("name"))]\n'
        'mid = [r for r in mid if not _bad_inst(r.get("name"))]\n'
        'print(f"  额外剔除机构号后 ok {len(ok)} / mid {len(mid)}")\n\n'
        'picked = ok + mid', 1)

t = t.replace("est = len(picked) * 15 * 0.15",
              "est = len(picked) / 6.7  # B站实测 6.7 个账号/小时")
t = t.replace('print(f"\\n预估采集: {len(picked)} 个 × 15 视频 ≈ {est:.0f} 小时（约 {est/24:.1f} 天）")',
              'print(f"\\n预估采集: {len(picked)} 个账号 ≈ {est:.0f} 小时（约 {est/24:.1f} 天）")')
f.write_text(t, encoding="utf-8")
print("已修正")
