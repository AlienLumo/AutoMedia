# -*- coding: utf-8 -*-
"""调试：为什么 captcha_hit 会误报？打印 URL 与命中的元素。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=True,
        viewport={"width": 1280, "height": 800},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    print("URL:", page.url)
    print("TITLE:", page.title()[:80])

    for key in ("verify", "captcha", "secsdk", "challenge"):
        if key in page.url.lower():
            print(f"  URL 命中: {key}")

    sels = ('iframe[src*="captcha"]', 'div[id*="captcha"]', 'div[class*="captcha"]',
            '#captcha_container', 'div[class*="vc-captcha"]')
    for sel in sels:
        try:
            el = page.query_selector(sel)
            if el:
                vis = el.is_visible()
                print(f"  命中选择器: {sel}  visible={vis}  "
                      f"html={el.inner_html()[:80]!r}")
        except Exception as e:
            print(f"  {sel} 查询异常 {e}")

    # cookie 概览
    names = sorted({c.get("name") for c in ctx.cookies()})
    print("cookie 数量:", len(names))
    print("登录类 cookie:", [n for n in names if n in
                          ("sessionid", "sessionid_ss", "sid_tt", "uid_tt", "passport_assist_user")])
    ctx.close()

