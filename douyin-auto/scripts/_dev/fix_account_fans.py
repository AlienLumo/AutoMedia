# -*- coding: utf-8 -*-
"""从 detail 接口的 author 对象取真实粉丝数，并修正账号目录名。"""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT, DATA

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
BASE = DATA / "douyin"

from patchright.sync_api import sync_playwright

acct = sorted([p for p in BASE.iterdir() if p.is_dir()], key=lambda p: -p.stat().st_mtime)[0]
vids = [v.name for v in acct.iterdir() if v.is_dir()]
if not vids:
    print("无作品目录"); sys.exit(1)
vid = vids[0]
print("账号目录:", acct.name, " 用作品", vid, "取作者信息")

detail = {}

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    def on_resp(r):
        try:
            if "/aweme/detail/" in r.url:
                detail.update(r.json() or {})
        except Exception:
            pass
    page.on("response", on_resp)
    page.goto(f"https://www.douyin.com/video/{vid}", wait_until="domcontentloaded",
              timeout=90000)
    page.wait_for_timeout(7000)
    ctx.close()

aw = (detail.get("aweme_detail") or {})
au = aw.get("author") or {}
fans = au.get("follower_count")
nick = au.get("nickname")
print(f"作者: {nick}  粉丝: {fans}")
print("author 全部字段:", {k: au.get(k) for k in
      ("nickname", "follower_count", "total_favorited", "aweme_count",
       "following_count", "signature")})

if fans and nick:
    tag = f"{fans/10000:.1f}万" if fans >= 10000 else str(fans)
    newname = f"{re.sub(r'[\\\\/:*?\"<>|]', '_', nick)[:30]}_{tag}"
    target = acct.parent / newname
    if target != acct and not target.exists():
        acct.rename(target)
        print(f"目录已重命名 → {newname}")
        acct = target
    ap = acct / "_account.json"
    data = json.loads(ap.read_text(encoding="utf-8"))
    data["fans"] = fans
    data["nickname"] = nick
    data["author_total_favorited"] = au.get("total_favorited")
    data["author_aweme_count"] = au.get("aweme_count")
    data["author_signature"] = au.get("signature")
    ap.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("_account.json 已更新")

