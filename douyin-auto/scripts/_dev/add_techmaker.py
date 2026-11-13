# -*- coding: utf-8 -*-
"""新增「科技创客」主题：自制 AI Agent / 机器人 / 电路硬件。
   并让 run_dual_after_search.ps1 支持 -Themes 参数。
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SCRIPTS

S = SCRIPTS

# ---------- 1) 新增主题 ----------
f = S / "douyin_find_by_video.py"
t = f.read_text(encoding="utf-8")

NEW = '''    "科技创客": [
        "AI Agent", "智能体搭建", "本地部署大模型", "AI工作流", "自制AI",
        "自制机器人", "DIY机器人", "开源机器人", "机器狗", "机械臂",
        "电路设计", "PCB设计", "单片机", "STM32", "树莓派",
        "Arduino", "ESP32", "嵌入式开发", "开源硬件", "自制硬件",
    ],
'''

if '"科技创客"' not in t:
    t = t.replace('THEMES = {\n', 'THEMES = {\n' + NEW, 1)
    f.write_text(t, encoding="utf-8")
    print("douyin_find_by_video.py: 已新增「科技创客」主题（20 个关键词）")
else:
    print("「科技创客」主题已存在")

# ---------- 2) run_dual_after_search.ps1 支持 -Themes ----------
f2 = S / "run_dual_after_search.ps1"
t2 = f2.read_text(encoding="utf-8")
if "-Themes" not in t2:
    t2 = t2.replace(
        "    [switch]$SkipSearch",
        "    [string]$Themes = '创客',\n    [switch]$SkipSearch")
    t2 = t2.replace(
        "--gap $SearchGap --min-fans 100000 --scroll 2",
        "--gap $SearchGap --min-fans 100000 --scroll 2 --themes '$Themes'")
    t2 = t2.replace(
        "--themes \"创客\" --split 2",
        "--themes $Themes --split 2")
    f2.write_text(t2, encoding="utf-8")
    print("run_dual_after_search.ps1: 已支持 -Themes")
else:
    print("run_dual_after_search.ps1: -Themes 已存在")

