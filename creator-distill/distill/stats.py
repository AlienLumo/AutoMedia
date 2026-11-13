# -*- coding: utf-8 -*-
"""stats.py — 账号画像统计（平台无关）。"""
import statistics
from collections import Counter


def _nums(works, key):
    out = []
    for w in works:
        v = (w.get("metrics") or {}).get(key)
        if isinstance(v, (int, float)) and v >= 0:
            out.append(v)
    return out


def build_stats(data):
    works = data.get("works") or []
    likes = _nums(works, "like")
    comments = _nums(works, "comment")
    collects = _nums(works, "collect")
    videos = [w for w in works if w.get("format") == "video"]
    images = [w for w in works if w.get("format") == "image_text"]
    dates = [w.get("published_at") for w in works if w.get("published_at")]
    durations = [w.get("duration_sec") for w in works if w.get("duration_sec")]

    def med(xs):
        return int(statistics.median(xs)) if xs else 0

    top = sorted(works, key=lambda w: -((w.get("metrics") or {}).get("like") or 0))[:10]
    like_med = med(likes)
    viral = [w for w in works if like_med and ((w.get("metrics") or {}).get("like") or 0) >= like_med * 5]
    return {
        "works": len(works),
        "videos": len(videos),
        "image_text": len(images),
        "like_median": like_med,
        "like_max": max(likes) if likes else 0,
        "like_total": sum(likes),
        "comment_median": med(comments),
        "collect_median": med(collects),
        "viral_count": len(viral),
        "date_first": min(dates) if dates else "",
        "date_last": max(dates) if dates else "",
        "duration_median": med(durations),
        "top": [{"title": w.get("title", ""), "like": (w.get("metrics") or {}).get("like"),
                 "url": w.get("url", "")} for w in top],
        "tag_counter": Counter(t for w in works for t in (w.get("tags") or [])).most_common(20),
    }
