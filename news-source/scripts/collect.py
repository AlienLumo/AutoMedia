#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect.py — 抓取当日事件原文：抓取 → 提取正文 → 落盘到 1信息源/<日期>/<事件>/

用法：
  python collect.py                        # 用 config/events/<NEWS_DATE>.json（默认 261111）
  python collect.py --date 261115          # 指定日期（读同日期的事件配置）
  python collect.py --events <path.json>   # 指定任意事件配置
"""
import argparse
import html as H
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except Exception:
    requests = None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import DATE, day_dir, events_config  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def load_events(path=None):
    """事件配置 → {slug: {title, links: [(label, url), ...]}}"""
    p = Path(path) if path else events_config()
    data = json.loads(p.read_text(encoding="utf-8"))
    return {slug: {"title": ev["title"],
                   "links": [tuple(x) for x in ev["links"]]}
            for slug, ev in data["events"].items()}


def fetch(url):
    if requests is None:
        return None
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
                         timeout=25, allow_redirects=True)
        return r
    except Exception as e:
        return None


def extract_text(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?is)<noscript.*?</noscript>", " ", html)
    # 块级标签换行
    html = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|section|article|br)>", "\n", html)
    html = re.sub(r"(?is)<br\s*/?>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = H.unescape(html)
    lines = [re.sub(r"[ \t\u3000]+", " ", l).strip() for l in txt.splitlines()]
    lines = [l for l in lines if len(l) >= 8]
    # 去重相邻重复行
    out, prev = [], None
    for l in lines:
        if l != prev:
            out.append(l)
        prev = l
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="抓取当日事件原文")
    ap.add_argument("--date", default="", help="日期目录，6 位（默认取 NEWS_DATE 或 261111）")
    ap.add_argument("--events", default="", help="事件配置 json（默认 config/events/<日期>.json）")
    a = ap.parse_args()

    date = a.date or DATE
    base = day_dir(date)
    events = load_events(a.events or events_config(date))

    base.mkdir(parents=True, exist_ok=True)
    index = []
    for slug, ev in events.items():
        d = base / slug
        (d / "原文").mkdir(parents=True, exist_ok=True)
        (d / "raw").mkdir(parents=True, exist_ok=True)
        meta = []
        for label, url in ev["links"]:
            r = fetch(url)
            status = getattr(r, "status_code", "ERR") if r is not None else "ERR"
            text, raw = "", ""
            if r is not None and status == 200:
                raw = r.text
                text = extract_text(raw)
                (d / "raw" / f"{label}.html").write_text(raw, encoding="utf-8", errors="replace")
            if text:
                body = (f"# {ev['title']} · {label}\n\n"
                        f"- URL: {url}\n- 抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                        f"- 状态: {status}\n- 正文字数: {len(text)}\n\n---\n\n{text}")
                (d / "原文" / f"{label}.md").write_text(body, encoding="utf-8")
            meta.append({"label": label, "url": url, "status": status, "chars": len(text),
                         "file": f"原文/{label}.md" if text else ""})
            print(f"  [{slug}] {label:<20} {status} chars={len(text)}")
            time.sleep(0.4)
        (d / "links.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        index.append({"slug": slug, "title": ev["title"], "links": len(meta),
                      "ok": sum(1 for m in meta if m["chars"] > 200)})
    (base / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n完成:", sum(i["ok"] for i in index), "/", sum(i["links"] for i in index), "个链接有正文")


if __name__ == "__main__":
    main()
