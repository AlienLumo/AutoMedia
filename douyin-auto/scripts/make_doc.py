# -*- coding: utf-8 -*-
"""把某账号的字幕文案整理成 Markdown + Word 文档（脚本生成，零 token 消耗）。"""
import json
import re
from pathlib import Path
from _paths import DATA

ACCT = DATA / "douyin" / "蓝星智人_2.2万"
OUT_MD = ACCT / "_蓝星智人字幕合集.md"
OUT_DOCX = ACCT / "_蓝星智人字幕合集.docx"


def fmt(n):
    n = n or 0
    return f"{n/10000:.1f}万" if n >= 10000 else str(n)


acc_file = ACCT / "_account.json"
acc = json.loads(acc_file.read_text(encoding="utf-8")) if acc_file.exists() else {}

vids = []
for v in sorted([x for x in ACCT.iterdir() if x.is_dir()]):
    mp, tp = v / "meta.json", v / "transcript.zh.txt"
    if not mp.exists():
        continue
    m = json.loads(mp.read_text(encoding="utf-8"))
    text = tp.read_text(encoding="utf-8").strip() if tp.exists() else ""
    cm_file = v / "comments.jsonl"
    cms = []
    if cm_file.exists():
        for line in cm_file.read_text(encoding="utf-8").splitlines()[:5]:
            try:
                c = json.loads(line)
                cms.append({"user": c.get("user") or "", "text": (c.get("text") or "").strip(),
                            "digg": c.get("digg_count") or 0})
            except Exception:
                pass
    if not text:
        continue
    vids.append({"id": v.name, "desc": (m.get("desc") or "").replace("\n", " ").strip(),
                 "digg": m.get("digg_count") or 0, "cmn": m.get("comment_count") or 0,
                 "coll": m.get("collect_count") or 0, "share": m.get("share_count") or 0,
                 "dur": (m.get("duration_ms") or 0) // 1000,
                 "date": (m.get("publish") or "")[:10],
                 "text": text, "cms": cms,
                 "chars": len(text.replace("\n", ""))})

if not acc.get("author_total_favorited"):
    for _v in vids:
        _mp = ACCT / _v["id"] / "meta.json"
        if _mp.exists():
            _m = json.loads(_mp.read_text(encoding="utf-8"))
            if _m.get("author_total_favorited"):
                acc["author_total_favorited"] = _m["author_total_favorited"]
                break

vids.sort(key=lambda x: -x["digg"])
total_chars = sum(v["chars"] for v in vids)
total_dur = sum(v["dur"] for v in vids)

# ---------- Markdown ----------
L = []
L.append(f"# {acc.get('nickname', '抖音账号')} · 字幕文案合集\n")
L.append(f"- 账号：{acc.get('nickname', '')}")
L.append(f"- 粉丝：{fmt(acc.get('fans'))}")
L.append(f"- 总获赞：{fmt(acc.get('author_total_favorited'))}")
L.append(f"- 主页：{acc.get('url', '')}")
L.append(f"- 简介：{(acc.get('author_signature') or '').replace(chr(10), ' / ')}")
L.append(f"- 收录视频：**{len(vids)} 个**，字幕合计 **{total_chars} 字**，"
         f"视频总时长 **{total_dur//60} 分 {total_dur%60} 秒**")
L.append(f"- 整理时间：2026-11-02")
L.append("\n---\n")

L.append("## 目录\n")
for i, v in enumerate(vids, 1):
    t = v["desc"][:34] or v["id"]
    L.append(f"{i}. {t}（赞 {fmt(v['digg'])}，{v['chars']} 字）")
L.append("\n---\n")

for i, v in enumerate(vids, 1):
    L.append(f"## {i}. {v['desc'] or v['id']}\n")
    L.append(f"| 项目 | 数据 |")
    L.append(f"|---|---|")
    L.append(f"| 点赞 | {fmt(v['digg'])} |")
    L.append(f"| 评论 | {fmt(v['cmn'])} |")
    L.append(f"| 收藏 | {fmt(v['coll'])} |")
    L.append(f"| 分享 | {fmt(v['share'])} |")
    L.append(f"| 时长 | {v['dur']} 秒 |")
    L.append(f"| 发布 | {v['date']} |")
    L.append(f"| 字幕字数 | {v['chars']} |")
    L.append(f"| aweme_id | {v['id']} |")
    L.append("")
    L.append("**字幕全文**\n")
    for line in v["text"].split("\n"):
        line = line.strip()
        if line:
            L.append(f"- {line}")
    L.append("")
    if v["cms"]:
        L.append("**热门评论（前 5 条）**\n")
        for c in v["cms"]:
            L.append(f"- `{c['user']}`：{c['text']}（赞 {c['digg']}）")
        L.append("")
    L.append("---\n")

L.append(f"\n> 本文档由脚本从 1AMdata 原始采集数据生成，共 {len(vids)} 个视频、{total_chars} 字字幕。")
OUT_MD.write_text("\n".join(L), encoding="utf-8")
print(f"MD={OUT_MD}  size={OUT_MD.stat().st_size/1024:.0f}KB")

# ---------- Word ----------
try:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)

    doc.add_heading(f"{acc.get('nickname','抖音账号')} · 字幕文案合集", level=0)
    for line in [
        f"账号：{acc.get('nickname','')}",
        f"粉丝：{fmt(acc.get('fans'))}　　总获赞：{fmt(acc.get('author_total_favorited'))}",
        f"主页：{acc.get('url','')}",
        f"简介：{(acc.get('author_signature') or '').replace(chr(10), ' / ')}",
        f"收录视频：{len(vids)} 个　字幕合计：{total_chars} 字　总时长：{total_dur//60}分{total_dur%60}秒",
        "整理时间：2026-11-02",
    ]:
        doc.add_paragraph(line)

    for i, v in enumerate(vids, 1):
        doc.add_heading(f"{i}. {v['desc'] or v['id']}", level=1)
        doc.add_paragraph(
            f"点赞 {fmt(v['digg'])}　评论 {fmt(v['cmn'])}　收藏 {fmt(v['coll'])}　"
            f"分享 {fmt(v['share'])}　时长 {v['dur']}s　发布 {v['date']}　字幕 {v['chars']} 字")
        doc.add_heading("字幕全文", level=2)
        for line in v["text"].split("\n"):
            line = line.strip()
            if line:
                doc.add_paragraph(line, style="List Bullet")
        if v["cms"]:
            doc.add_heading("热门评论（前 5 条）", level=2)
            for c in v["cms"]:
                doc.add_paragraph(f"{c['user']}：{c['text']}（赞 {c['digg']}）",
                                  style="List Bullet")
    doc.save(str(OUT_DOCX))
    print(f"DOCX={OUT_DOCX}  size={OUT_DOCX.stat().st_size/1024:.0f}KB")
except Exception as e:
    print(f"DOCX 生成失败: {type(e).__name__}: {e}")

print(f"SUMMARY videos={len(vids)} chars={total_chars} dur={total_dur}s")
