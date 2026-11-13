# -*- coding: utf-8 -*-
"""拦截抖音 web 的 aweme detail 接口响应，验证能否一次拿到全部结构化字段。"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
VID = sys.argv[1] if len(sys.argv) > 1 else "7623382584165509989"

from patchright.sync_api import sync_playwright

captured = []

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def on_resp(r):
        u = r.url
        if any(k in u for k in ("aweme/detail", "aweme/v1/web/aweme", "/aweme/post/", "comment/list")):
            try:
                if "json" in (r.headers or {}).get("content-type", ""):
                    captured.append((u.split("?")[0][-60:], r.json()))
            except Exception:
                pass
    page.on("response", on_resp)

    page.goto(f"https://www.douyin.com/video/{VID}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)
    try:
        page.click("video", timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(6000)

    print("拦截到接口:", len(captured))
    for name, j in captured:
        print(f"\n--- {name}")
        keys = list(j.keys())[:8] if isinstance(j, dict) else type(j)
        print("   顶层键:", keys)
        aw = None
        if isinstance(j, dict):
            if "aweme_detail" in j:
                aw = j["aweme_detail"]
            elif "aweme_list" in j and j["aweme_list"]:
                aw = j["aweme_list"][0]
        if aw:
            print("   aweme 键:", list(aw.keys())[:20])
            st = aw.get("statistics") or {}
            print("   统计:", {k: st.get(k) for k in
                              ("digg_count", "comment_count", "collect_count",
                               "share_count", "play_count")})
            print("   文案:", (aw.get("desc") or "")[:80])
            print("   作者:", (aw.get("author") or {}).get("nickname"),
                  "| sec_uid:", ((aw.get("author") or {}).get("sec_uid") or "")[:30])
            v = aw.get("video") or {}
            pa = (v.get("play_addr") or {}).get("url_list") or []
            print("   play_addr 数量:", len(pa))
            for u in pa[:2]:
                print("      ", u[:110])
            print("   时长:", v.get("duration"), "ms")
            print("   封面:", ((v.get("cover") or {}).get("url_list") or [None])[0])
    ctx.close()

