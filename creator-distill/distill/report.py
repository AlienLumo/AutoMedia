# -*- coding: utf-8 -*-
"""report.py — 生成蒸馏报告（Markdown）。视觉分析留给 AI 读图后补充。"""
from datetime import datetime
from pathlib import Path

from .stats import build_stats
from .titles import build_titles
from .structure import build_structure


def build_report(data, out_dir):
    stats = build_stats(data)
    titles = build_titles(data.get("works") or [])
    struct = build_structure(data.get("works") or [])
    creator = data.get("creator") or {}
    platform = data.get("platform", "")
    frames = []
    for w in data.get("works") or []:
        if w.get("frames"):
            frames.append((w.get("title", ""), w.get("frames")))
    lines = []
    A = lines.append
    A(f"# 蒸馏：{creator.get('name','')}（{platform}）")
    A("")
    A(f"- 采集时间：{data.get('collected_at','')}")
    A(f"- 作品数：{stats['works']}（视频 {stats['videos']} / 图文 {stats['image_text']}）")
    A(f"- 点赞：中位 {stats['like_median']} / 最高 {stats['like_max']} / 合计 {stats['like_total']}")
    A(f"- 评论中位：{stats['comment_median']}；收藏中位：{stats['collect_median']}")
    A(f"- 爆款（≥5 倍中位）：{stats['viral_count']} 条")
    A(f"- 日期范围：{stats['date_first']} → {stats['date_last']}")
    A(f"- 视频时长中位：{stats['duration_median']} 秒；逐字稿样本：{struct['count']} 条"
      f"（平均语速 {struct['avg_speak_rate']} 字/秒）")
    A("")
    A("## 1. 标题公式")
    if titles:
        A(f"- 长度：{titles['len_min']}–{titles['len_max']}，中位 {titles['len_median']} 字")
        A("- 句式命中：" + "、".join(f"{k} {v}/{titles['count']}" for k, v in titles["patterns"].items()))
        A("- 高频词：" + "、".join(titles["top_terms"][:18]))
        A("- 样例：")
        for t in titles["samples"][:8]:
            A(f"  - {t}")
    else:
        A("（样本不足）")
    A("")
    A("## 2. 高赞榜")
    for i, w in enumerate(stats["top"][:8], 1):
        A(f"{i}. {w['like']} 赞 · {w['title'][:56]} · {w['url']}")
    A("")
    suspicious = [w for w in (data.get("works") or []) if w.get("likely_reupload")]
    if suspicious:
        A("## 2.5 来源与可疑信号")
        A(f"- {len(suspicious)} 条抽样的 ASR 含「订阅/打赏/栏目/点赞」等片尾话术，"
          "疑似搬运或二创；这类账号的标题与正文可能不同源，蒸馏时要分开看。")
        for w in suspicious[:5]:
            A(f"  - {w.get('title','')[:44]}（{w.get('url','')}）")
        A("")
    A("## 3. 文案结构（逐字稿）")
    A("- 注：ASR 存在同音误差与断句误差，只用于结构判断，引用原话前需核对原视频。")
    if struct["samples"]:
        for s in struct["samples"][:3]:
            A(f"### {s['title'][:50]}")
            A(f"- 时长 {s['duration']}s / {s['chars']} 字 / 语速 {s['speak_rate']} 字/秒")
            A(f"- 钩子：{s['hook']}")
            A(f"- 首句：{s['first_sentence']}")
            A(f"- 收尾：{s['last_sentence']}")
            A(f"- 原理词：{'、'.join(s['principles']) if s['principles'] else '未命中'}")
            A(f"- 分段（每 60s）：" + " ｜ ".join(x[:40] for x in s["sections"][:5]))
            A("")
    else:
        A("（无逐字稿：视频号需要 ASR，或本次未开启）")
    A("")
    A("## 4. 视觉分析（AI 读图后补充）")
    A("")
    A("抽帧文件见 `works/<id>/frames/`；建议先看 `contact_sheet.jpg`，再补看 1–2 张单帧。")
    A("")
    A("待分析清单：")
    A("- 封面/首帧：大字标题、人物、对比、色块、信息密度")
    A("- 画面风格：动画/实拍/图文卡；配色与统一性")
    A("- 字幕样式：位置、字号、描边、关键词高亮")
    A("- 节奏：抽帧之间的场景变化（是否 3–5 秒一换）")
    A("- 可复用视觉模板：一句话总结 + 3 条可执行建议")
    A("")
    if frames:
        A("### 已抽帧清单")
        for title, fs in frames:
            A(f"- {title[:40]}")
            for f in fs[-2:]:
                A(f"  - `{f}`")
    A("")
    A("## 5. 可复用模板（待填/迭代）")
    A("- 标题：___")
    A("- 开场 15 秒：___")
    A("- 中段结构：___")
    A("- 收尾 CTA：___")
    A("- 视觉：___")
    md = "\n".join(lines)
    p = Path(out_dir) / "report.md"
    p.write_text(md, encoding="utf-8")
    return p, md
