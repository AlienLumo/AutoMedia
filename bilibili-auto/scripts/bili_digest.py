#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_digest.py — 把当天监听到的内容做成日报，推送飞书 + 落盘 Markdown。

用法：
  python bili_digest.py                 # 今天
  python bili_digest.py --date 2026-11-08 --no-push
  python bili_digest.py --top 15
"""
import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watch_common import (DIGESTS, VIDEOS, Lock, fmt_play, load_config, load_json,
                          log, read_inbox, load_roster, STATE)

GROUPS = [
    ("AI工具/模型", ["ai ", "ai_", "aigc", "大模型", "模型", "deepseek", "gpt", "claude",
                  "gemini", "openai", "agent", "智能体", "mcp", "skill", "工作流",
                  "提示词", "绘画", "视频生成", "sora", "可灵", "即梦", "多模态",
                  "token", "api", "微调", "rag", "cursor", "comfyui"]),
    ("硬件/创客", ["单片机", "嵌入式", "树莓派", "arduino", "esp32", "diy", "自制",
                 "机器人", "机械臂", "3d打印", "pcb", "电路", "无人机", "显卡", "显存",
                 "装机", "硬件"]),
    ("商业/财经", ["创业", "商业", "公司", "财报", "股票", "股市", "基金", "投资",
                 "副业", "变现", "赚钱", "电商", "出海", "融资", "经济", "黄金"]),
    ("科技/数码", ["苹果", "iphone", "华为", "小米", "发布", "测评", "评测", "开箱",
                 "黑科技", "新品", "芯片", "半导体", "发布会"]),
    ("局势/时政", ["美国", "特朗普", "俄乌", "中美", "军事", "台海", "局势", "战争",
                 "国际"]),
    ("科研/学术", ["论文", "科研", "物理", "化学", "生物", "医学", "材料", "alphafold",
                 "ai4science", "实验室"]),
    ("教程/课程", ["教程", "入门", "教学", "课程", "保姆", "手把手", "零基础"]),
]


def classify(title, tags):
    t = f"{title or ''} {tags or ''}".lower()
    for name, kws in GROUPS:
        if any(k in t for k in kws):
            return name
    return "其他"


def load_meta(proc, bvid):
    d = (proc.get(bvid) or {}).get("dir")
    if not d:
        return None
    p = VIDEOS / d / "meta.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def build(date, top_n):
    items = read_inbox(date=date)
    proc = load_json(STATE / "processed.json", {})
    cfg = load_config()
    roster = {u["mid"] for u in load_roster()}
    only_roster = bool(cfg["digest"].get("roster_only", True))
    window_h = int(cfg["digest"].get("window_hours", 24))
    cutoff_ts = time.time() - window_h * 3600
    rows, sub_ok, dropped = [], 0, 0
    for it in items:
        if int(it.get("discovered_ts") or 0) < cutoff_ts:
            dropped += 1
            continue
        if only_roster and it.get("mid") not in roster:
            dropped += 1
            continue
        if (proc.get(it["bvid"]) or {}).get("status") in ("skipped", "expired"):
            dropped += 1
            continue
        meta = load_meta(proc, it["bvid"])
        st = proc.get(it["bvid"]) or {}
        m = {
            "bvid": it["bvid"], "title": (meta or {}).get("title") or it.get("title") or "",
            "up": (meta or {}).get("owner") or it.get("up") or "",
            "mid": it.get("mid"), "play": (meta or {}).get("view") or it.get("play") or 0,
            "heat": (meta or {}).get("heat") or 0,
            "tags": " ".join((meta or {}).get("tags") or []),
            "source": it.get("source"), "kw": it.get("kw"),
            "pubdate_str": (meta or {}).get("pubdate_str") or "",
            "has_sub": bool(st.get("sub")),
        }
        if m["has_sub"]:
            sub_ok += 1
        m["group"] = classify(m["title"], m["tags"])
        rows.append(m)

    rows.sort(key=lambda x: (-(x["heat"] or 0), -(x["play"] or 0)))
    up_new = [r for r in rows if r["mid"] not in roster]
    kwc = Counter(r["kw"] for r in rows if r.get("kw"))
    grp = defaultdict(list)
    for r in rows:
        grp[r["group"]].append(r)

    d = datetime.strptime(date, "%Y-%m-%d")
    head = f"🛰 B站泛AI/科技日报 · {d.strftime('%Y-%m-%d')}"
    lines = [head, "━━━━━━━━━━━━━━",
             "📊 今日概览",
             f"新增视频 {len(rows)} 条｜UP跟踪 {sum(1 for r in rows if r['source']=='up')}"
             f"｜关键词 {sum(1 for r in rows if r['source']=='kw')}",
             f"覆盖创作者 {len({r['mid'] for r in rows})} 个｜已抓字幕 {sub_ok}"
             f"｜新号 {len(up_new)} 个"
             + (f"｜过滤 {dropped} 条（名单外/过期）" if dropped else ""), ""]
    lines.append(f"🔥 热度 Top {min(top_n, len(rows))}")
    for i, r in enumerate(rows[:top_n], 1):
        lines.append(f"{i}. {r['title'][:46]}（{r['up'][:12]} · 播放 {fmt_play(r['play'])}）")
        lines.append(f"   https://www.bilibili.com/video/{r['bvid']}")
    lines.append("")
    lines.append("🧩 分类速览")
    for name, _ in GROUPS + [("其他", [])]:
        g = grp.get(name) or []
        if not g:
            continue
        lines.append(f"· {name}（{len(g)}）：" + " / ".join(x["title"][:22] for x in g[:5]))
    if up_new:
        lines.append("")
        lines.append("🆕 名单外新号")
        for r in up_new[:8]:
            lines.append(f"· {r['up'][:16]}（播放 {fmt_play(r['play'])}）{r['title'][:28]}")
    if kwc:
        lines.append("")
        lines.append("🔑 关键词命中：" + "、".join(f"{k}×{v}" for k, v in kwc.most_common(10)))
    lines += ["━━━━━━━━━━━━━━",
              f"窗口：{date} 全天 · 由 bilibili-auto watch 生成"]
    text = "\n".join(lines)
    md = [f"# {head}", "", f"- 新增视频：{len(rows)}", f"- 已抓字幕：{sub_ok}",
          f"- 新号：{len(up_new)}", "", "## Top"]
    for i, r in enumerate(rows[:top_n], 1):
        md.append(f"{i}. [{r['title']}](https://www.bilibili.com/video/{r['bvid']}) — "
                  f"{r['up']} · 播放 {fmt_play(r['play'])} · {r['group']}")
    md += ["", "## 分类"]
    for name, _ in GROUPS + [("其他", [])]:
        g = grp.get(name) or []
        if g:
            md.append(f"### {name}（{len(g)}）")
            for r in g[:20]:
                md.append(f"- [{r['title']}](https://www.bilibili.com/video/{r['bvid']}) — "
                          f"{r['up']} · {fmt_play(r['play'])}")
    return text, "\n".join(md), len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--force-push", action="store_true", dest="force_push")
    a = ap.parse_args()
    date = a.date or datetime.now().strftime("%Y-%m-%d")
    cfg = load_config()
    top_n = a.top or int(cfg["digest"].get("top") or 12)

    text, md, nrows = build(date, top_n)
    DIGESTS.mkdir(parents=True, exist_ok=True)
    (DIGESTS / f"{date}.md").write_text(md, encoding="utf-8")
    try:
        print(f"[digest] 写入 {DIGESTS / (date + '.md')}", file=sys.stderr)
        print(text[:1200])
    except Exception:          # pythonw 下 stdout/stderr 可能不可用
        pass

    if nrows == 0 and not a.no_push and not a.force_push:
        log("[digest] 今日无新增，跳过推送", "digest")
        print("PUSH-SKIP no new items")
        return 0
    if not a.no_push and cfg["digest"].get("push", True):
        from feishu_push import send_text
        ok, detail = send_text(text)
        log(f"[digest] 飞书推送 {'成功' if ok else '失败'}: {detail}", "digest")
        print(("PUSH-OK " if ok else "PUSH-FAIL ") + detail)
        if not ok:
            return 2
    return 0


if __name__ == "__main__":
    with Lock("digest"):
        raise SystemExit(main())

