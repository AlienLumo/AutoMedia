# -*- coding: utf-8 -*-
"""report.py — 为任意已采集的抖音账号目录生成 Markdown 报告。

用法：python report.py --dir "<项目根>/1AMdata/douyin/<账号目录>"
不给 --dir 时，取 1AMdata/douyin 下最新的账号目录。
"""
import argparse
import json
from pathlib import Path
from _paths import DATA

BASE = DATA / "douyin"


def fmt(n):
    n = n or 0
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="")
    ap.add_argument("--top", type=int, default=3, help="字幕样例条数")
    a = ap.parse_args()

    acct = Path(a.dir) if a.dir else sorted(
        [p for p in BASE.iterdir() if p.is_dir()],
        key=lambda p: -p.stat().st_mtime)[0]
    acc_file = acct / "_account.json"
    acc = json.loads(acc_file.read_text(encoding="utf-8")) if acc_file.exists() else {}

    rows, total_chars, total_cm = [], 0, 0
    for v in sorted([x for x in acct.iterdir() if x.is_dir()]):
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
        rows.append({"id": v.name, "desc": (m.get("desc") or "").replace("\n", " ")[:70],
                     "digg": m.get("digg_count") or 0, "cmn": m.get("comment_count") or 0,
                     "coll": m.get("collect_count") or 0, "share": m.get("share_count") or 0,
                     "dur": (m.get("duration_ms") or 0) // 1000, "chars": len(txt),
                     "ncm": ncm, "date": (m.get("publish") or "")[:10], "text": txt})
    rows.sort(key=lambda x: -x["digg"])

    L = [f"# 抖音账号采集报告：{acc.get('nickname') or acct.name}\n",
         f"- 采集时间：{acc.get('time','')}",
         f"- 主页：{acc.get('url','')}",
         f"- 粉丝：**{fmt(acc.get('fans'))}**（{acc.get('fans')}）",
         f"- 总获赞：{fmt(acc.get('author_total_favorited'))}",
         f"- 简介：{(acc.get('author_signature') or '').replace(chr(10),' / ')}",
         f"- 主页作品总数：{acc.get('works_found')}",
         f"- 本次采集：**{len(rows)} 个作品**（置顶+播放量Top10，另加最新5，去重）",
         f"- 数据：评论 {total_cm} 条、字幕 {total_chars} 字，未保存视频文件",
         "", "## 作品清单（按点赞降序）\n",
         "| # | 文案 | 点赞 | 评论 | 收藏 | 分享 | 时长 | 字幕字数 | 发布 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        L.append(f'| {i} | {r["desc"]} | {fmt(r["digg"])} | {fmt(r["cmn"])} | '
                 f'{fmt(r["coll"])} | {fmt(r["share"])} | {r["dur"]}s | {r["chars"]} | {r["date"]} |')
    L += ["", "## 数据位置\n", "```", str(acct), "```", ""]
    L += [f"## 字幕样例（点赞最高 {a.top} 条）\n"]
    for r in rows[:a.top]:
        L += [f'### {r["desc"]}（赞 {fmt(r["digg"])}）\n', "```",
              r["text"][:800].strip(), "```", ""]
    out = BASE / f"_report_{acct.name}.md"
    out.write_text("\n".join(L), encoding="utf-8")

    # 只打印极简摘要（给模型看的，省 token）
    print(f"REPORT={out}")
    print(f"ACCOUNT={acc.get('nickname')} FANS={acc.get('fans')} "
          f"VIDEOS={len(rows)} COMMENTS={total_cm} CHARS={total_chars}")


if __name__ == "__main__":
    main()
