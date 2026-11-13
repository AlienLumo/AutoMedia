# -*- coding: utf-8 -*-
"""from_video.py — 给一个视频链接（或分享短链），反查出作者主页并可选采集。

覆盖场景：
  ③ 给某个视频 → 查询并采集这个博主主页的其他视频

用法：
  python from_video.py --url "https://v.douyin.com/xxxx/"                    # 只解析作者
  python from_video.py --url "https://v.douyin.com/xxxx/" --collect          # 解析+采集
  python from_video.py --url "https://www.douyin.com/video/7623..." --collect --top-play 10 --latest 5
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
SCRIPTS = Path(__file__).resolve().parent
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')


def captcha_hit(page):
    try:
        u = (page.url or "").lower()
        if any(k in u for k in ("verify", "captcha", "secsdk", "challenge")):
            return True
        if "验证码" in (page.title() or ""):
            return True
        for sel in CAPTCHA_SELECTORS:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
    except Exception:
        pass
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--profile", default="")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--top-play", type=int, default=10, dest="top_play")
    ap.add_argument("--latest", type=int, default=5)
    ap.add_argument("--comments", type=int, default=20)
    ap.add_argument("--gap", type=int, default=55)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    from patchright.sync_api import sync_playwright

    prof = Path(a.profile) if a.profile else PROFILE
    detail = {}

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(prof), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
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

        print(f"[1] 打开 {a.url}", flush=True)
        page.goto(a.url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(6000)
        final = page.url
        print(f"    重定向到: {final[:90]}", flush=True)
        if captcha_hit(page):
            print("  ⚠ 验证码，终止", flush=True)
            ctx.close()
            return 2

        # 如果直接是主页
        m = re.search(r"/user/([A-Za-z0-9_\-]{20,})", final)
        profile_url = f"https://www.douyin.com/user/{m.group(1)}" if m else None
        video_id = None

        if not profile_url:
            m = re.search(r"/video/(\d{10,})", final)
            if m:
                video_id = m.group(1)
                print(f"[2] 是作品页 {video_id}，等 detail 接口…", flush=True)
                if not detail:
                    page.wait_for_timeout(4000)
                aw = (detail.get("aweme_detail") or {})
                au = aw.get("author") or {}
                sec = au.get("sec_uid")
                print(f"    作者: {au.get('nickname')}  sec_uid={sec}", flush=True)
                print(f"    文案: {(aw.get('desc') or '')[:60]}", flush=True)
                if sec:
                    profile_url = f"https://www.douyin.com/user/{sec}"

        if not profile_url:
            # 兜底：页面上找作者主页链接
            try:
                hrefs = page.evaluate("""() => [...document.querySelectorAll('a[href*="/user/"]')]
                    .map(e=>e.getAttribute('href')).slice(0,12)""")
                for h in hrefs:
                    mm = re.search(r"/user/([A-Za-z0-9_\-]{20,})", h or "")
                    if mm and mm.group(1) != "self":
                        profile_url = ("https://www.douyin.com" + h) if h.startswith("/") else h
                        break
            except Exception:
                pass

        ctx.close()

    print("\n=== 结果 ===")
    print(json.dumps({"video_id": video_id, "profile_url": profile_url}, ensure_ascii=False))
    if not profile_url:
        print("❌ 未能解析出作者主页")
        return 3

    if a.collect:
        print(f"\n[3] 开始采集该博主（top{a.top_play}+latest{a.latest}）", flush=True)
        py = sys.executable
        cmd = [py, str(SCRIPTS / "douyin_collect.py"),
               "--url", profile_url,
               "--top-play", str(a.top_play), "--latest", str(a.latest),
               "--comments", str(a.comments), "--save-video", "no",
               "--gap", str(a.gap)]
        if a.profile:
            cmd += ["--profile", a.profile]
        r = subprocess.run(cmd)
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

