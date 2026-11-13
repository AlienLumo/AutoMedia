# -*- coding: utf-8 -*-
r"""修复 play_num/num 被日期字符串击穿的 bug。

   '....2024.09.01' → float() ValueError → 整个采集崩溃 exit=1
修复：
  1) 正则要求以数字开头：(\d+(?:\.\d+)?) 而不是 ([\d\.]+)
  2) float 转换加 try/except 兜底
"""
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SCRIPTS

S = SCRIPTS

# ---------- douyin_collect.py ----------
f = S / "douyin_collect.py"
t = f.read_text(encoding="utf-8")

old = '''def play_num(s):
    if s is None:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"([\\d\\.]+)\\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) *
               {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))'''
new = '''def play_num(s):
    """把 '12.3万' / '1.2亿' / '3456' 转成 int。对日期类脏字符串返回 0。"""
    if s is None:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"(\\d+(?:\\.\\d+)?)\\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    try:
        v = float(m.group(1))
    except (TypeError, ValueError):
        return 0
    return int(v * {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))'''

if old in t:
    t = t.replace(old, new, 1)
    print("douyin_collect.py: play_num 已加固")
else:
    print("douyin_collect.py: 未匹配 play_num（可能已修）")

# 卡片数字提取正则也收紧，避免产生 '....2024.09.01'
t = t.replace(
    'nums = re.findall(r"([\\d\\.]+\\s*[万亿]?)",',
    'nums = re.findall(r"(\\d+(?:\\.\\d+)?\\s*[万亿]?)",')
f.write_text(t, encoding="utf-8")

# ---------- douyin_find_by_video.py ----------
f2 = S / "douyin_find_by_video.py"
t2 = f2.read_text(encoding="utf-8")
if "def num(s):" in t2:
    old2 = '''def num(s):
    if not s:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"([\\d\\.]+)\\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) *
               {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))'''
    new2 = '''def num(s):
    if not s:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"(\\d+(?:\\.\\d+)?)\\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    try:
        v = float(m.group(1))
    except (TypeError, ValueError):
        return 0
    return int(v * {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))'''
    if old2 in t2:
        t2 = t2.replace(old2, new2, 1)
        f2.write_text(t2, encoding="utf-8")
        print("douyin_find_by_video.py: num 已加固")
    else:
        print("douyin_find_by_video.py: 未匹配 num")

# ---------- 自查：用问题字符串测试 ----------
import sys
sys.path.insert(0, str(S))
import importlib.util
spec = importlib.util.spec_from_file_location("dc", S / "douyin_collect.py")
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except Exception as e:
    print("导入失败:", e)
    raise SystemExit(0)

for s in ["....2024.09.01", "2024.09.01", "12.3万", "1.2亿", "3456", "", None, "1.5w"]:
    print(f"  play_num({s!r}) = {m.play_num(s)}")
