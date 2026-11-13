# -*- coding: utf-8 -*-
"""structure.py — 从逐字稿拆结构：钩子 / 分段 / 收尾 / 语速（平台无关）。"""
import re

PRINCIPLE_WORDS = ["效应", "定律", "原理", "实验", "心理学", "社会学", "经济学", "认知",
                   "偏差", "理论", "机制", "模型", "研究", "数据"]


def _text(work):
    tr = work.get("transcript") or {}
    return tr.get("text") or ""


def _segments(work):
    return (work.get("transcript") or {}).get("segments") or []


def analyze_work(work):
    text = _text(work)
    segs = _segments(work)
    dur = work.get("duration_sec") or 0
    # 句子来源：优先按字幕分段，其次按标点
    sentences = [s.get("text", "").strip() for s in segs if s.get("text")]
    if not sentences:
        sentences = [x for x in re.split(r"[。！？!?]", text) if x.strip()]
    hook = ""
    if segs:
        hook = "".join(s.get("text", "") for s in segs if (s.get("start") or 0) < 15).strip()
    if not hook:
        hook = text[:80]
    sections = []
    for s in segs:
        idx = int((s.get("start") or 0) // 60)
        while len(sections) <= idx:
            sections.append([])
        sections[idx].append(s.get("text", ""))
    sections = ["".join(x).strip() for x in sections if x]
    principles = [w for w in PRINCIPLE_WORDS if w in text]
    rate = (len(text) / dur) if dur else 0
    return {
        "work_id": work.get("work_id"), "title": work.get("title", ""),
        "duration": dur, "chars": len(text), "speak_rate": round(rate, 2),
        "hook": hook[:120], "sections": sections[:8],
        "first_sentence": (sentences[0] if sentences else "")[:100],
        "last_sentence": (sentences[-1] if sentences else "")[:100],
        "principles": principles,
    }


def build_structure(works):
    samples = [analyze_work(w) for w in works if _text(w)]
    return {
        "samples": samples,
        "count": len(samples),
        "avg_speak_rate": round(sum(s["speak_rate"] for s in samples) / len(samples), 2) if samples else 0,
        "principle_hits": sorted({p for s in samples for p in s["principles"]}),
    }
