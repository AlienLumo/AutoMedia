# -*- coding: utf-8 -*-
"""给 play_num 加日期形态守卫。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "douyin_collect.py"
t = f.read_text(encoding="utf-8")

anchor = '    s = str(s).strip().lower().replace(" ", "")\n'
guard = anchor + (
    '    # 排除日期形态（2024.09.01 / 2024-09-01），否则会被当成播放量\n'
    '    if re.match(r"^\\d{4}[\\.\\-/]\\d{1,2}[\\.\\-/]\\d{1,2}", s):\n'
    '        return 0\n'
)

if "排除日期形态" in t:
    print("已存在日期守卫")
else:
    # 只替换 play_num 内的那一次（函数定义后第一次出现）
    i = t.find("def play_num(s):")
    j = t.find(anchor, i)
    assert i >= 0 and j >= 0, "未找到 play_num 或 anchor"
    t = t[:j] + guard + t[j + len(anchor):]
    f.write_text(t, encoding="utf-8")
    print("已给 play_num 加日期守卫")

# 验证
import importlib.util
spec = importlib.util.spec_from_file_location("dc", str(f))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
for s in ["2024.09.01", "....2024.09.01", "12.3万", "3456", "1.2亿", "2024-9-1"]:
    print(f"  play_num({s!r}) = {m.play_num(s)}")
