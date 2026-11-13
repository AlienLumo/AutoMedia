# -*- coding: utf-8 -*-
"""探测抖音搜索页的博主链接真实格式。"""
import sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
KW = sys.argv[1] if len(sys.argv) > 1 else "AI工具"

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    for typ in ("user", "video"):
        url = f"https://www.douyin.com/search/{quote(KW)}?type={typ}"
        print(f"\n=== type={typ} ===")
        print("URL:", url)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print("  goto err", str(e)[:70]); continue
        page.wait_for_timeout(5000)
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(2500)
        print("  TITLE:", (page.title() or "")[:60])

        e2e = page.evaluate("""() => {
            const s=new Set();
            document.querySelectorAll('[data-e2e]').forEach(e=>s.add(e.getAttribute('data-e2e')));
            return [...s].slice(0,30);
        }""")
        print("  data-e2e:", e2e)

        info = page.evaluate("""() => {
            const users=[], vids=[];
            document.querySelectorAll('a[href]').forEach(a=>{
                const h=a.getAttribute('href')||'';
                if(h.includes('/user/')) users.push(h.slice(0,90));
                if(h.includes('/video/')) vids.push(h.slice(0,90));
            });
            return {users:[...new Set(users)].slice(0,8), vids:[...new Set(vids)].slice(0,8)};
        }""")
        print("  user 链接样例:", info["users"])
        print("  video 链接样例:", info["vids"])

        # 搜索结果条目文本样例
        items = page.evaluate("""() => {
            const out=[];
            document.querySelectorAll('li, [data-e2e="scroll-list-item"]').forEach(el=>{
                const t=(el.innerText||'').trim();
                if(t && t.length<200 && out.length<6) out.push(t.replace(/\\n/g,' | ').slice(0,120));
            });
            return out;
        }""")
        print("  条目样例:")
        for i in items:
            print("    ", i)
    ctx.close()

