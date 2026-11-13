# -*- coding: utf-8 -*-
"""测试不同 device_scale_factor 的截图清晰度；并把 Wayback 快照存档落盘。"""
import re, sys, urllib.request, json, html as H
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir, CHROME as CHROME_PATH

BASE = day_dir()
CHROME = str(CHROME_PATH)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# 1) Wayback 快照
url = "https://www.nytimes.com/2026/11/10/technology/anthropic-ipo-google-amazon.html"
snap = "https://web.archive.org/web/20261110232754/" + url
try:
    req = urllib.request.Request(snap, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read().decode("utf-8", "ignore")
    txt = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", raw)
    txt = re.sub(r"(?s)<[^>]+>", " ", txt)
    txt = H.unescape(txt)
    txt = re.sub(r"[ \t\u3000]+", " ", txt)
    lines = [l.strip() for l in txt.splitlines() if len(l.strip()) > 30]
    body = "\n".join(lines[:120])
    out = BASE / "01_anthropic-ipo" / "原文" / "存档_nyt-google-amazon.md"
    out.write_text(f"# NYT · Amazon/Google 将因 Anthropic IPO 大赚（Wayback 快照）\n\n- 快照时间: 20261110232754\n- 原 URL: {url}\n- 说明: 付费墙原页 403；本文件来自 Internet Archive 公开快照，仅供事实核查，引用请以原文为准。\n\n---\n\n{body}", encoding="utf-8")
    print("wayback saved chars", len(body))
except Exception as e:
    print("wayback fail", e)

# 2) dsf 对比
from patchright.sync_api import sync_playwright
test_url = "https://www.cnbc.com/2026/11/10/anthropic-ipo-shares-invest.html"
outdir = BASE / "01_anthropic-ipo" / "截图"
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME, headless=True, args=["--no-sandbox", "--disable-gpu"])
    for dsf, tag in ((1, "dsf1"), (2, "dsf2")):
        pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=dsf)
        try:
            pg.goto(test_url, timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            p = outdir / f"清晰度对比_{tag}.png"
            pg.screenshot(path=str(p))
            print(tag, "screenshot", p.stat().st_size // 1024, "KB")
        finally:
            pg.close()
    b.close()
