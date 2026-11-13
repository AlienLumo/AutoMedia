# -*- coding: utf-8 -*-
"""解析抖音分享短链 → 博主主页 URL。

支持两种情况：
  - 短链跳转到 /user/<sec_uid>  → 直接返回主页
  - 短链跳转到 /video/<id>       → 拦截 detail 接口拿 author.sec_uid，拼出主页
"""
import json
import re
import sys
import time
from pathlib import Path
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
SHORT = sys.argv[1] if len(sys.argv) > 1 else "https://v.douyin.com/ImUfhS7p4So/"

from patchright.sync_api import sync_playwright

detail = {}

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def on_resp(r):
        try:
            if "/aweme/detail/" in r.url:
                detail.update(r.json() or {})
        except Exception:
            pass
    page.on("response", on_resp)

    print(f"[1] 打开短链 {SHORT}")
    page.goto(SHORT, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(6000)

    final = page.url
    print(f"    重定向到: {final}")

    profile_url = None
    m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", final)
    if m and m.group(1) != "self":
        profile_url = f"https://www.douyin.com/user/{m.group(1)}"

    if not profile_url:
        m = re.search(r"/video/(\d{10,})", final)
        video_id = m.group(1) if m else None
        if not video_id:
            # 可能是弹窗/中间页，再等等看
            page.wait_for_timeout(4000)
            final = page.url
            print(f"    再次检查: {final}")
            m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", final)
            if m:
                profile_url = f"https://www.douyin.com/user/{m.group(1)}"
            m2 = re.search(r"/video/(\d{10,})", final)
            video_id = video_id or (m2.group(1) if m2 else None)

        if video_id and not profile_url:
            print(f"[2] 是作品页，作品 id={video_id}；拦截 detail 取作者…")
            if not detail:
                page.wait_for_timeout(4000)
            aw = (detail.get("aweme_detail") or {})
            au = aw.get("author") or {}
            sec = au.get("sec_uid")
            print(f"    作者: {au.get('nickname')}  sec_uid={sec}")
            print(f"    文案: {(aw.get('desc') or '')[:60]}")
            if sec:
                profile_url = f"https://www.douyin.com/user/{sec}"

    # 兜底：页面上找作者主页链接
    if not profile_url:
        try:
            hrefs = page.evaluate("""() => [...document.querySelectorAll('a[href*="/user/"]')]
                .map(a=>a.getAttribute('href')).slice(0,10)""")
            for h in hrefs:
                mm = re.search(r"/user/([A-Za-z0-9_\-]{20,})", h or "")
                if mm and mm.group(1) != "self":
                    profile_url = "https://www.douyin.com" + h if h.startswith("/") else h
                    break
        except Exception:
            pass

    print("\n=== 结果 ===")
    print(json.dumps({"final_url": final, "profile_url": profile_url},
                     ensure_ascii=False))
    ctx.close()

if not profile_url:
    sys.exit(4)

