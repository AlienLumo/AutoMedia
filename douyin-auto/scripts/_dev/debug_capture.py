# -*- coding: utf-8 -*-
"""逐步调试：为什么 SearchCapture 抓不到 aweme_info。"""
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

log = {"urls": [], "search_item": 0, "parse_ok": 0, "parse_fail": 0,
       "aweme_info": 0, "data_len": [], "sample_keys": None}

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def on_resp(r):
        u = r.url
        if "search" in u:
            log["urls"].append(u.split("?")[0])
        if "/aweme/v1/web/search/item/" in u:
            log["search_item"] += 1
            try:
                j = r.json()
                log["parse_ok"] += 1
            except Exception as e:
                log["parse_fail"] += 1
                print("  JSON 解析失败:", type(e).__name__, str(e)[:80])
                try:
                    body = r.text()
                    print("  原始前 120 字符:", body[:120])
                except Exception:
                    pass
                return
            data = j.get("data") or []
            log["data_len"].append(len(data))
            for d in data:
                aw = d.get("aweme_info")
                if aw:
                    log["aweme_info"] += 1
                    if log["sample_keys"] is None:
                        log["sample_keys"] = list(aw.keys())[:15]

    page.on("response", on_resp)
    url = f"https://www.douyin.com/search/{quote(KW)}?type=video"
    print("URL:", url)
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(8000)
    page.mouse.wheel(0, 700)
    page.wait_for_timeout(4000)

    print("\n=== 结果 ===")
    print("  search/item 响应数:", log["search_item"])
    print("  JSON 解析成功/失败:", log["parse_ok"], "/", log["parse_fail"])
    print("  每条 data 长度:", log["data_len"])
    print("  aweme_info 总数:", log["aweme_info"])
    print("  首条 aweme 键:", log["sample_keys"])
    print("\n  涉及 search 的 URL:")
    for u in dict.fromkeys(log["urls"]):
        print("   ", u)
    ctx.close()

