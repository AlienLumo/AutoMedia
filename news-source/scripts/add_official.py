# -*- coding: utf-8 -*-
"""补充官方动态页（Anthropic / OpenAI / Google）到对应事件目录。"""
import json, re, sys, html as H
from datetime import datetime
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir

BASE = day_dir()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

JOBS = [
    ("01_anthropic-ipo", "anthropic-news", "https://www.anthropic.com/news"),
    ("02_anthropic-office", "anthropic-news", "https://www.anthropic.com/news"),
    ("03_claude-52", "anthropic-news", "https://www.anthropic.com/news"),
    ("04_gemini4-carbon", "google-blog-ai", "https://blog.google/technology/ai/"),
    ("06_openai-business", "openai-news", "https://openai.com/news/"),
]


def extract(html):
    html = re.sub(r"(?is)<script.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?</style>", " ", html)
    html = re.sub(r"(?i)</(p|div|h[1-6]|li|tr|section|article)>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    txt = H.unescape(html)
    lines = [re.sub(r"[ \t\u3000]+", " ", l).strip() for l in txt.splitlines()]
    return "\n".join(l for l in lines if len(l) >= 8)


for slug, label, url in JOBS:
    d = BASE / slug
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
        status, txt = r.status_code, extract(r.text) if r.status_code == 200 else ""
    except Exception as e:
        status, txt = "ERR", ""
    if txt:
        body = (f"# 官方动态页 · {label}\n\n- URL: {url}\n- 抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"- 状态: {status}\n- 正文字数: {len(txt)}\n\n---\n\n{txt}")
        (d / "原文" / f"官方动态_{label}.md").write_text(body, encoding="utf-8")
        print(f"{slug}: {label} ok chars={len(txt)}")
    else:
        print(f"{slug}: {label} fail status={status}")
