# -*- coding: utf-8 -*-
"""探测抖音博主主页的真实 DOM 结构，用于写准提取选择器。"""
import sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.douyin.com/user/bncWhkZaPfgvbjC4nCUo"

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=True,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    page.mouse.wheel(0, 900)
    page.wait_for_timeout(3000)

    print("URL:", page.url)
    print("TITLE:", (page.title() or "")[:60])

    # 1) 页面里所有 data-e2e 属性
    e2e = page.evaluate("""() => {
        const s = new Set();
        document.querySelectorAll('[data-e2e]').forEach(e => s.add(e.getAttribute('data-e2e')));
        return [...s].sort();
    }""")
    print("\n[data-e2e] 共", len(e2e), "个:")
    print("  ", e2e[:40])

    # 2) 视频链接数量与样例
    vids = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('a[href*="/video/"]').forEach(a => {
            const href = a.getAttribute('href') || '';
            const m = href.match(/\\/video\\/(\\d+)/);
            if (!m) return;
            const img = a.querySelector('img');
            out.push({
                id: m[1],
                aria: (a.getAttribute('aria-label') || '').slice(0, 60),
                imgAlt: img ? (img.getAttribute('alt') || '').slice(0, 60) : '',
                text: (a.innerText || '').replace(/\\n/g, ' | ').slice(0, 80)
            });
        });
        return out.slice(0, 12);
    }""")
    print(f"\n[视频链接] 共 {len(vids)} 条（前12）:")
    for v in vids:
        print(f"   {v['id']}  aria={v['aria']!r}")
        print(f"        imgAlt={v['imgAlt']!r}")
        print(f"        text={v['text']!r}")

    # 3) 用户统计相关区块
    stats = page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[data-e2e]').forEach(e => {
            const t = (e.innerText || '').trim();
            if (/粉丝|获赞|关注|作品/.test(t) && t.length < 120) {
                out.push({e2e: e.getAttribute('data-e2e'), text: t.replace(/\\n/g,' | ')});
            }
        });
        return out.slice(0, 10);
    }""")
    print("\n[统计区块]:")
    for s in stats:
        print(f"   {s['e2e']}: {s['text']!r}")
    ctx.close()

