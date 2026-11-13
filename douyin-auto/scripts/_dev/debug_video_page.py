# -*- coding: utf-8 -*-
"""探测抖音作品页：真实媒体 URL 与互动数从哪来。"""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
VID = sys.argv[1] if len(sys.argv) > 1 else "7623382584165509989"

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    media = []
    def on_resp(r):
        u = r.url
        if any(k in u for k in ("douyinvod", "/video/tos", "m3u8", ".mp4", "web-video")):
            media.append((u[:120], (r.headers or {}).get("content-type", "")[:40]))
    page.on("response", on_resp)

    page.goto(f"https://www.douyin.com/video/{VID}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(4000)
    # 尝试点击播放
    try:
        page.click("video", timeout=5000)
    except Exception:
        pass
    page.wait_for_timeout(8000)

    print("TITLE:", (page.title() or "")[:50])
    print("\n[1] 网络媒体请求:", len(media))
    for u, ct in media[:8]:
        print("   ", ct, u)

    print("\n[2] video 元素状态")
    info = page.evaluate("""() => {
        const out=[];
        document.querySelectorAll('video').forEach(v=>{
            out.push({src:(v.src||'').slice(0,80), cur:(v.currentSrc||'').slice(0,80),
                      dur:v.duration, w:v.videoWidth, h:v.videoHeight,
                      paused:v.paused});
        });
        return out;
    }""")
    for i in info:
        print("   ", i)

    print("\n[3] 内嵌 JSON（RENDER_DATA / __INITIAL_STATE__ / SSR）")
    scripts = page.evaluate("""() => {
        const out=[];
        document.querySelectorAll('script').forEach(s=>{
            const t=s.textContent||'';
            if(t.length>500 && (t.includes('play_addr')||t.includes('url_list')||t.includes('aweme_id'))){
                out.push({id:s.id||'', len:t.length, head:t.slice(0,60)});
            }
        });
        return out;
    }""")
    for s in scripts:
        print("   ", s)

    print("\n[4] 从脚本里提取 play_addr")
    got = page.evaluate("""() => {
        const res={urls:[],stats:{}};
        document.querySelectorAll('script').forEach(s=>{
            const t=s.textContent||'';
            // play_addr url_list
            const m=t.match(/"play_addr":\\{[^}]*"url_list":\\[([^\\]]+)\\]/);
            if(m){ try{ res.urls = JSON.parse('['+m[1]+']').slice(0,3); }catch(e){} }
            for(const k of ['digg_count','comment_count','collect_count','share_count']){
                const mm=t.match(new RegExp('"'+k+'":(\\\\d+)'));
                if(mm) res.stats[k]=+mm[1];
            }
        });
        return res;
    }""")
    print("   统计:", got.get("stats"))
    for u in (got.get("urls") or [])[:3]:
        print("   url:", str(u)[:110])

    print("\n[5] 页面上「点赞」附近的数字")
    body = page.inner_text("body")[:4000]
    for kw in ("点赞", "评论", "收藏", "分享"):
        m = re.search(rf"([\d\.]+\s*[万亿]?)\s*{kw}", body)
        print(f"   {kw}: {m.group(1) if m else '未匹配'}")
    ctx.close()

