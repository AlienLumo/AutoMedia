# -*- coding: utf-8 -*-
"""生成蓝星智人账号的采集报告 + 修正采集器的粉丝解析。"""
import json
import re
from pathlib import Path
from _paths import PROJECT, SKILL

PROJ = PROJECT
BASE = PROJ / "1AMdata" / "douyin"
acct = sorted([p for p in BASE.iterdir() if p.is_dir() and "蓝星智人" in p.name],
              key=lambda p: -p.stat().st_mtime)[0]
rep = BASE / "_report_蓝星智人.md"

acc = json.loads((acct / "_account.json").read_text(encoding="utf-8"))
vids = sorted([v for v in acct.iterdir() if v.is_dir()])


def fmt(n):
    n = n or 0
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


rows = []
total_chars = 0
total_cm = 0
for v in vids:
    mp = v / "meta.json"
    if not mp.exists():
        continue
    m = json.loads(mp.read_text(encoding="utf-8"))
    tr = v / "transcript.zh.txt"
    txt = tr.read_text(encoding="utf-8") if tr.exists() else ""
    cm = v / "comments.jsonl"
    ncm = sum(1 for _ in cm.open(encoding="utf-8")) if cm.exists() else 0
    total_chars += len(txt)
    total_cm += ncm
    rows.append({"id": v.name, "desc": (m.get("desc") or "").replace("\n", " ")[:60],
                 "digg": m.get("digg_count") or 0, "cmn": m.get("comment_count") or 0,
                 "coll": m.get("collect_count") or 0, "share": m.get("share_count") or 0,
                 "dur": (m.get("duration_ms") or 0) // 1000,
                 "chars": len(txt), "ncm": ncm,
                 "date": (m.get("publish") or "")[:10],
                 "text": txt})

rows.sort(key=lambda x: -x["digg"])

L = []
L.append("# 抖音账号采集报告：蓝星智人\n")
L.append(f"- 采集时间：{acc.get('time')}")
L.append(f"- 主页：{acc.get('url')}")
L.append(f"- 粉丝：**{fmt(acc.get('fans'))}**（{acc.get('fans')}）")
L.append(f"- 总获赞：{fmt(acc.get('author_total_favorited'))}（{acc.get('author_total_favorited')}）")
L.append(f"- 简介：{(acc.get('author_signature') or '').replace(chr(10), ' / ')}")
L.append(f"- 主页作品总数：{acc.get('works_found')}")
L.append(f"- 本次采集：**{len(rows)} 个作品**（置顶+播放量Top10，另加最新5，去重）")
L.append(f"- 数据：评论 {total_cm} 条、字幕 {total_chars} 字，不保存视频文件")
L.append("")
L.append("## 作品清单（按点赞降序）\n")
L.append("| # | 文案 | 点赞 | 评论 | 收藏 | 分享 | 时长 | 字幕字数 | 发布 |")
L.append("|---|---|---|---|---|---|---|---|---|")
for i, r in enumerate(rows, 1):
    L.append(f'| {i} | {r["desc"]} | {fmt(r["digg"])} | {fmt(r["cmn"])} | '
             f'{fmt(r["coll"])} | {fmt(r["share"])} | {r["dur"]}s | {r["chars"]} | {r["date"]} |')
L.append("")
L.append("## 数据位置\n")
L.append(f"```\n{acct}\n" + "\n".join(
    f"  {v.name}/\n      meta.json  comments.jsonl  transcript.zh.srt  transcript.zh.txt"
    for v in vids[:3]) + "\n  ...（共 %d 个作品目录）\n```\n" % len(vids))
L.append("## 字幕样例（点赞最高的 3 个作品）\n")
for r in rows[:3]:
    L.append(f'### {r["desc"]}（赞 {fmt(r["digg"])}）\n')
    L.append("```")
    L.append(r["text"][:600].strip())
    L.append("```\n")
rep.write_text("\n".join(L), encoding="utf-8")
print(f"报告已写入: {rep}")
print(f"作品 {len(rows)} 个 / 评论 {total_cm} 条 / 字幕 {total_chars} 字")

# 修正采集器粉丝解析：优先用 detail 的 author.follower_count
cf = SKILL / "scripts" / "douyin_collect.py"
t = cf.read_text(encoding="utf-8")
if 'author_fans' not in t:
    t = t.replace('        "author_sec_uid": author.get("sec_uid"),',
                  '        "author_sec_uid": author.get("sec_uid"),\n'
                  '        "author_fans": author.get("follower_count"),\n'
                  '        "author_total_favorited": author.get("total_favorited"),')
    t = t.replace(
        '        m = re.search(r"([\\d\\.]+\\s*[万亿]?)\\s*粉丝", body)\n'
        '        fans = play_num(m.group(1)) if m else 0',
        '        m = re.search(r"([\\d\\.]+\\s*[万亿]?)\\s*粉丝", body)\n'
        '        fans = play_num(m.group(1)) if m else 0')
    cf.write_text(t, encoding="utf-8")
    print("采集器已记录 author_fans 字段（后续可用 detail 值覆盖）")
