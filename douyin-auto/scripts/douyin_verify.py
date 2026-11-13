#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""douyin_verify.py — 抖音「隔离验证」：最低风险地探测账号/网络环境的容忍度。

做什么：
  1. 用 patchright + 独立 profile 启动有头 Chromium（不碰主 profile）
  2. 打开 douyin.com，等待你扫码登录（首次）
  3. 依次访问 N 个博主主页，拟人化滚动
  4. 记录：是否加载成功、是否出现验证/滑块、可见作品数、耗时
  5. 结果追加写入 data/douyin-verify/verify-log.jsonl

不做任何批量抓取、不调接口、不下载、不评论。

用法：
  <项目根>\runtime\python\python.exe douyin_verify.py --runs 5
  （--runs 表示本次访问几个博主；每天跑一次，连续 3 天观察）
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
DATA = PROJECT / "data" / "douyin-verify"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
LOG = DATA / "verify-log.jsonl"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"

# 验证目标：抖音一些公开的、内容量大的博主（固定几个即可，避免随机搜索触发风控）
TARGETS = [
    ("https://www.douyin.com/user/MS4wLjABAAAA", "占位-需替换"),
]

# 验证码判定：只看 URL 与真实 DOM 元素，避免「验证码登录」这类正常文案误判
CAPTCHA_URL_KEYS = ("verify", "captcha", "secsdk", "challenge")
CAPTCHA_SELECTORS = (
    'iframe[src*="captcha"]', 'div[id*="captcha"]', 'div[class*="captcha"]',
    '#captcha_container', 'div[class*="vc-captcha"]',
)


def captcha_hit(page):
    """只有「URL 命中」或「验证码 iframe 可见」或「标题是验证码页」才算真命中。

    抖音正常页面会常驻一个隐藏的 captcha iframe（反爬 SDK 预加载），
    仅凭元素存在会持续误报。
    """
    try:
        u = (page.url or "").lower()
        if any(k in u for k in CAPTCHA_URL_KEYS):
            return True
        title = (page.title() or "")
        if "验证码" in title or "安全验证" in title:
            return True
        for sel in CAPTCHA_SELECTORS:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
    except Exception:
        pass
    return False


def human_pause(a=1.2, b=3.5):
    time.sleep(random.uniform(a, b))


def human_scroll(page, times=3):
    for _ in range(times):
        page.mouse.wheel(0, random.randint(300, 700))
        human_pause(0.8, 2.2)


LOGIN_COOKIES = {"sessionid", "sessionid_ss", "sid_tt", "passport_assist_user",
                 "uid_tt", "uid_tt_ss"}


def cookies_logged_in(ctx):
    try:
        names = {c.get("name") for c in ctx.cookies()}
        return bool(names & LOGIN_COOKIES), sorted(names & LOGIN_COOKIES)
    except Exception:
        return False, []


def detect(page, ctx=None):
    """返回 (logged_in, captcha_hit, video_count, title)"""
    body = ""
    try:
        body = page.inner_text("body")[:4000]
    except Exception:
        pass
    low = body.lower()
    captcha = captcha_hit(page)
    # 登录判定：出现「登录」按钮通常=未登录；出现头像/私信等=已登录
    ck_ok, ck_names = cookies_logged_in(ctx) if ctx is not None else (False, [])
    logged_in = ck_ok or (("登录" not in body[:600]) and ("抖音" in body))
    # 作品数量：找「作品」后跟数字，或「个作品」
    import re
    vc = 0
    m = re.search(r"作品[^\d]{0,6}(\d{1,6})", body)
    if m:
        vc = int(m.group(1))
    elif "作品" in body:
        vc = -1   # 有「作品」字样但没解析到数字
    title = page.title()[:80]
    return logged_in, captcha, vc, title


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="本次访问几个博主主页")
    ap.add_argument("--targets-file", default="", help="每行一个抖音主页 URL")
    ap.add_argument("--login-timeout", type=int, default=600, dest="login_timeout")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--probe-only", action="store_true", dest="probe_only",
                    help="只探测首页能否加载，不等待登录、不访问目标")
    ap.add_argument("--hold", type=int, default=0,
                    help="探测后保持窗口 N 秒（便于人工观察）")
    a = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    PROFILE.mkdir(parents=True, exist_ok=True)

    targets = []
    if a.targets_file and Path(a.targets_file).exists():
        targets = [(l.strip(), "") for l in Path(a.targets_file).read_text(
            encoding="utf-8").splitlines() if l.strip().startswith("http")]
    else:
        targets = [(u, n) for u, n in TARGETS if not n.startswith("占位")]
    if not targets:
        print("[warn] 没有有效目标 URL；先用 douyin.com 首页做一次环境探测")

    from patchright.sync_api import sync_playwright

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    rec = {"run_id": run_id, "ts": time.time(), "profile": str(PROFILE),
           "logged_in": None, "captcha": False, "targets": [], "verdict": ""}

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            executable_path=str(CHROME),
            headless=a.headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("[1] 打开抖音首页…")
        try:
            page.goto("https://www.douyin.com/", wait_until="domcontentloaded",
                      timeout=60000)
        except Exception as e:
            print(f"   首页加载失败: {str(e)[:80]}")
        human_pause(3, 5)
        logged_in, captcha, vc, title = detect(page, ctx)
        print(f"   登录={logged_in} 验证={captcha} 标题={title}")
        rec["logged_in"] = logged_in
        rec["captcha"] = captcha

        if a.probe_only:
            print(f"[probe] 首页探测完成：登录={logged_in} 验证={captcha} 标题={title}")
            if captcha:
                print("        ⚠ 匿名访问即触发验证/滑块 → 抖音对当前环境有较强风控")
            if a.hold:
                print(f"        保持窗口 {a.hold}s 供人工观察…")
                time.sleep(a.hold)
            with LOG.open("a", encoding="utf-8") as f:
                rec["verdict"] = "probe_captcha" if captcha else "probe_ok"
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            ctx.close()
            print(f"[结果] verdict={rec['verdict']}  日志={LOG}")
            return

        if not logged_in:
            print(f"[2] 未登录 → 请在浏览器里扫码登录（最多等 {a.login_timeout}s）")
            deadline = time.time() + a.login_timeout
            while time.time() < deadline:
                human_pause(4, 6)
                li, cap, _, _ = detect(page, ctx)
                if li:
                    logged_in = True
                    rec["logged_in"] = True
                    print("   已登录 ✅")
                    break
                if cap:
                    rec["captcha"] = True
                    print("   ⚠ 检测到验证码/滑块")
                    break
            if not logged_in:
                rec["verdict"] = "login_timeout"
                print("[!] 登录超时，记录后退出")

        # 访问目标主页
        for i, (url, name) in enumerate(targets[:a.runs], 1):
            t0 = time.time()
            item = {"url": url, "name": name, "ok": False, "captcha": False,
                    "videos": 0, "title": "", "secs": 0}
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                human_pause(2.5, 4.5)
                human_scroll(page, 3)
                li, cap, vc, ti = detect(page, ctx)
                item.update(ok=True, captcha=cap, videos=vc, title=ti)
                rec["captcha"] = rec["captcha"] or cap
                print(f"   [{i}] {name or url[:40]} ok 作品={vc} 验证={cap}")
            except Exception as e:
                item["error"] = str(e)[:100]
                print(f"   [{i}] {name or url[:40]} 失败 {str(e)[:60]}")
            item["secs"] = round(time.time() - t0, 1)
            rec["targets"].append(item)
            human_pause(4, 9)   # 主页之间长间隔，像人一样

        if not rec["verdict"]:
            if rec["captcha"]:
                rec["verdict"] = "captcha_detected"
            elif rec["logged_in"] and all(t["ok"] for t in rec["targets"]):
                rec["verdict"] = "ok"
            else:
                rec["verdict"] = "partial"
        ctx.close()

    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n[结果] verdict={rec['verdict']} 验证={rec['captcha']} "
          f"目标成功={sum(1 for t in rec['targets'] if t['ok'])}/{len(rec['targets'])}")
    print(f"[日志] {LOG}")


if __name__ == "__main__":
    main()

