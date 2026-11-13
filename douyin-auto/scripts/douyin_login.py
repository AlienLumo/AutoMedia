# -*- coding: utf-8 -*-
"""douyin_login.py — 用指定 profile 打开抖音并等待扫码登录。

用法：
  python douyin_login.py --profile "D:\\...\\douyin-account2-profile" --timeout 600

成功判据：cookie 中出现 sessionid（登录态）。
"""
import argparse
import time
from pathlib import Path
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
LOGIN_COOKIES = {"sessionid", "sessionid_ss", "sid_tt", "uid_tt"}

ap = argparse.ArgumentParser()
ap.add_argument("--profile", required=True)
ap.add_argument("--timeout", type=int, default=600)
a = ap.parse_args()

prof = Path(a.profile)
prof.mkdir(parents=True, exist_ok=True)

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(prof), executable_path=str(CHROME), headless=False,
        viewport={"width": 1200, "height": 860},
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=90000)
    print("[login] 浏览器已打开，请在窗口内扫码登录…", flush=True)

    deadline = time.time() + a.timeout
    ok = False
    while time.time() < deadline:
        try:
            names = {c.get("name") for c in ctx.cookies()}
            if names & LOGIN_COOKIES:
                ok = True
                nick = ""
                try:
                    j = page.evaluate("""async () => {
                        const r = await fetch('https://www.douyin.com/aweme/v1/web/im/user/info/',
                                              {credentials:'include'});
                        return await r.json().catch(()=>null);
                    }""")
                except Exception:
                    j = None
                print(f"[login] 检测到登录态（{sorted(names & LOGIN_COOKIES)}）", flush=True)
                break
        except Exception:
            pass
        time.sleep(5)

    if ok:
        print("[login] 登录成功，profile 已保存：", prof, flush=True)
        ctx.storage_state(path=str(prof / "state.json"))
    else:
        print("[login] 超时未检测到登录", flush=True)
    ctx.close()

