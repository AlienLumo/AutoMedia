# -*- coding: utf-8 -*-
"""解码抖音作品页的 RENDER_DATA，映射出结构化字段路径。"""
import json
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
    page.goto(f"https://www.douyin.com/video/{VID}", wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(5000)

    res = page.evaluate("""() => {
        const el = document.getElementById('RENDER_DATA');
        if(!el) return {err:'no RENDER_DATA'};
        let raw = el.textContent || '';
        let obj = null;
        try { obj = JSON.parse(decodeURIComponent(raw)); }
        catch(e){ return {err:'parse:'+e.message, head: raw.slice(0,80)}; }

        const findPaths = (o, pred, path='', acc=[], depth=0) => {
            if(depth>12 || acc.length>60) return acc;
            if(o && typeof o==='object'){
                for(const k in o){
                    const v=o[k], p=path?path+'.'+k:k;
                    if(pred(k,v)) acc.push([p, typeof v==='object'?JSON.stringify(v).slice(0,80):String(v).slice(0,80)]);
                    findPaths(v, pred, p, acc, depth+1);
                }
            }
            return acc;
        };
        const stats = findPaths(obj, (k,v)=>['digg_count','comment_count','collect_count','share_count','aweme_id','desc'].includes(k));
        const authors = findPaths(obj, (k,v)=>['nickname','unique_id','sec_uid'].includes(k));
        const media = findPaths(obj, (k,v)=>k==='play_addr'||k==='download_addr'||k==='bit_rate');
        return {topKeys: Object.keys(obj).slice(0,10), stats: stats.slice(0,20),
                authors: authors.slice(0,10), media: media.slice(0,6)};
    }""")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3500])
    ctx.close()

