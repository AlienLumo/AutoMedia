# -*- coding: utf-8 -*-
"""探测抖音视频搜索接口：拦截 search API，确认能拿到作者信息。"""
import json
import sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
KW = sys.argv[1] if len(sys.argv) > 1 else "创业"

from patchright.sync_api import sync_playwright

hits = []

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def on_resp(r):
        u = r.url
        if "search" in u and ("aweme" in u or "/web/" in u) and "json" in (r.headers or {}).get("content-type", ""):
            try:
                hits.append((u.split("?")[0], r.json()))
            except Exception:
                pass
    page.on("response", on_resp)

    url = f"https://www.douyin.com/search/{quote(KW)}?type=video"
    print("URL:", url)
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)
    page.mouse.wheel(0, 800)
    page.wait_for_timeout(3000)
    print("TITLE:", (page.title() or "")[:60])

    print(f"\n拦截到 {len(hits)} 个 search 响应")
    for name, j in hits:
        print(f"\n--- {name}")
        if isinstance(j, dict):
            print("  顶层键:", list(j.keys())[:10])
            data = j.get("data")
            if isinstance(data, list) and data:
                print(f"  data 条数: {len(data)}")
                first = data[0]
                print("  首条键:", list(first.keys())[:12] if isinstance(first, dict) else type(first))
                # 找 aweme_info
                aw = first.get("aweme_info") if isinstance(first, dict) else None
                if aw:
                    au = aw.get("author") or {}
                    st = aw.get("statistics") or {}
                    print("  作者:", au.get("nickname"), "| sec_uid:", (au.get("sec_uid") or "")[:20],
                          "| 粉丝:", au.get("follower_count"))
                    print("  视频:", (aw.get("desc") or "")[:50])
                    print("  数据: 赞", st.get("digg_count"), "评", st.get("comment_count"))
                    print("  aweme 键样例:", [k for k in list(aw.keys())[:40] if "author" in k or "video" in k][:6])
    ctx.close()

