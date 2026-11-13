# -*- coding: utf-8 -*-
"""为双账号并行做准备：
  1) douyin_collect.py 增加 --profile 参数
  2) build_targets.py 增加 --themes / --split
  3) run_queue.ps1 增加 -Profile / -StatusTag；给了 Profile 时不等其它实例（不同 profile 独立并行）
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SCRIPTS

S = SCRIPTS

# ---------- 1) douyin_collect.py: --profile ----------
f = S / "douyin_collect.py"
t = f.read_text(encoding="utf-8")
if '"--profile"' not in t:
    t = t.replace(
        '    ap.add_argument("--headless", action="store_true")',
        '    ap.add_argument("--profile", default="",\n'
        '                    help="浏览器 profile 目录（双账号并行时用不同目录）")\n'
        '    ap.add_argument("--headless", action="store_true")', 1)
    t = t.replace(
        '            user_data_dir=str(PROFILE), executable_path=str(CHROME),',
        '            user_data_dir=str(Path(a.profile) if a.profile else PROFILE),\n'
        '            executable_path=str(CHROME),', 1)
    f.write_text(t, encoding="utf-8")
    print("douyin_collect.py: 已加 --profile")
else:
    print("douyin_collect.py: --profile 已存在")

# ---------- 2) build_targets.py ----------
f2 = S / "build_targets.py"
t2 = f2.read_text(encoding="utf-8")
if "--themes" not in t2:
    t2 = t2.replace(
        'WANT = ("创客", "创业")\nMIN_FANS = 100000',
        '''import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument("--themes", default="创客")
_ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
_ap.add_argument("--split", type=int, default=1)
_args = _ap.parse_args()

WANT = tuple(x.strip() for x in _args.themes.split(",") if x.strip())
MIN_FANS = _args.min_fans''')
    t2 = t2.replace(
        '''OUT.write_text("\\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}' for x in rows) + "\\n",
                encoding="utf-8")''',
        '''if _args.split > 1:
    for part in range(_args.split):
        sub = [x for i, x in enumerate(rows) if i % _args.split == part]
        p = OUT.with_name(f"queue_creators_p{part + 1}.txt")
        p.write_text("\\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}' for x in sub) + "\\n",
                     encoding="utf-8")
        print(f"SPLIT={p}  count={len(sub)}")
else:
    OUT.write_text("\\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}' for x in rows) + "\\n",
                   encoding="utf-8")''')
    f2.write_text(t2, encoding="utf-8")
    print("build_targets.py: 已加 --themes/--split")
else:
    print("build_targets.py: 参数已存在")

# ---------- 3) run_queue.ps1 ----------
f3 = S / "run_queue.ps1"
t3 = f3.read_text(encoding="utf-8")
if "-Profile" not in t3:
    t3 = t3.replace(
        "    [int]$MaxWaitMinutes = 360",
        "    [int]$MaxWaitMinutes = 360,\n"
        "    [string]$Profile = '',\n"
        "    [string]$StatusTag = ''")
    t3 = t3.replace(
        "$Status = Join-Path $LogDir 'queue-status.txt'",
        '$Status = Join-Path $LogDir ("queue-status" + $(if($StatusTag){"-$StatusTag"}else{""}) + ".txt")\n'
        "$ProfArg = @()\n"
        "if ($Profile) { $ProfArg = @('--profile', $Profile) }")
    # 给了 Profile：不同 profile 是独立浏览器，不必互相等待
    t3 = t3.replace(
        "function Wait-Idle {\n    $deadline",
        "function Wait-Idle {\n    if ($Profile) { return $true }\n    $deadline")
    t3 = t3.replace(
        "--mode batch 2>&1 |",
        "--mode batch @ProfArg 2>&1 |")
    f3.write_text(t3, encoding="utf-8")
    print("run_queue.ps1: 已加 -Profile / -StatusTag（不同 profile 并行）")
else:
    print("run_queue.ps1: 参数已存在")
