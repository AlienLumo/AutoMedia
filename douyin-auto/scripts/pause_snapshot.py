# -*- coding: utf-8 -*-
"""生成暂停时的状态快照，写入 1AMdata/暂停状态.md"""
import json
import re
from datetime import datetime
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
OUT = PROJ / "1AMdata/暂停状态.md"


def count_dy():
    base = PROJ / "1AMdata/douyin"
    acc = v = s = c = 0
    for d in base.iterdir():
        if not d.is_dir():
            continue
        vs = [x for x in d.iterdir() if x.is_dir()]
        if not vs:
            continue
        acc += 1
        v += len(vs)
        for x in vs:
            if (x / "transcript.zh.txt").exists():
                s += 1
            cf = x / "comments.jsonl"
            if cf.exists():
                try:
                    c += sum(1 for _ in cf.open(encoding="utf-8"))
                except Exception:
                    pass
    return acc, v, s, c


def count_bili():
    conf = SKILL.parent / "bilibili-auto/config"
    total = sum(1 for ln in (conf / "prefix_map.tsv").read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.startswith("#"))
    st = PROJ / "1AMdata/_state/deep_collect.json"
    d = json.loads(st.read_text(encoding="utf-8"))
    a = d.get("accounts") or {}
    fin = sum(1 for x in a.values() if x.get("stage") == "finished")
    tv = sum(len(x.get("done") or []) for x in a.values() if x.get("stage") == "finished")
    tc = sum(x.get("total_cm", 0) or 0 for x in a.values() if x.get("stage") == "finished")
    return total, fin, tv, tc


bt, bf, bv, bc = count_bili()
da, dv, ds, dc = count_dy()

L = [f"# 采集暂停状态\n",
     f"> 暂停时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
     "## B站\n",
     "| 项 | 数值 |",
     "|---|---|",
     f"| 名单总数 | {bt} |",
     f"| 已完成账号 | **{bf}**（{bf/bt*100:.1f}%）|",
     f"| 剩余 | {bt - bf} |",
     f"| 视频 | **{bv:,}** |",
     f"| 评论 | **{bc:,}** |",
     "",
     "> 采集器已报「all accounts finished」，计划任务每 25 分钟触发但只做 skip，不会实际采集。",
     "",
     "## 抖音\n",
     "| 项 | 数值 |",
     "|---|---|",
     f"| 已采账号 | **{da}** |",
     f"| 视频 | **{dv:,}** |",
     f"| 字幕 | **{ds:,}**（{ds/dv*100:.1f}%）|",
     f"| 评论 | {dc:,} |",
     "",
     "### 中断时正在跑的队列",
     "| 队列文件 | 总数 | 已完成 | 剩余 |",
     "|---|---|---|---|",
     "| queue_talk_p2_resume5.txt | 21 | 18 | **3** |",
     "| queue_makeup_p1.txt | 18 | 4 | **14** |",
     "",
     "> 另有 queue_makeup_p2.txt（18 个）尚未开始。",
     "",
     "## 进程状态\n",
     "- 抖音采集进程：**已全部停止**",
     "- 抖音队列进程：**已全部停止**",
     "- Chrome（抖音 profile）：**已关闭**",
     "- B站 连续运行器：**已停止**",
     "",
     "## 恢复方式\n",
     "对助手说「继续采集」即可。恢复时会：",
     "1. 抖音：重新启动两个队列（续跑剩余 17 个 + 未开始的 18 个）",
     "2. B站：825/826 已基本完成，如需补采剩余账号或新增名单再启动",
]
OUT.write_text("\n".join(L), encoding="utf-8")
print(f"B站: {bf}/{bt} 账号, {bv} 视频, {bc} 评论")
print(f"抖音: {da} 账号, {dv} 视频, {ds} 字幕, {dc} 评论")
print(f"\n状态文件: {OUT}")
