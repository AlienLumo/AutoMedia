# -*- coding: utf-8 -*-
"""douyin_probe.py — 抖音主链路探测：搜索关键词 → 提取博主 → 访问主页 → 抓作品标题。

只读、低频、拟人化。用于验证「查找相关领域博主 + 监测更新 + 内容提取」这条链路。
结果写入 data/douyin-verify/probe-<时间>.json

用法：
  python douyin_probe.py --keyword "AI工具" --visits 3
  python douyin_probe.py --url https://www.douyin.com/user/xxx --visits 1
"""
import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from _paths import PROJECT

RUNTIME = PROJECT / "runtime"
DATA = PROJECT / "data" / "douyin-verify"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"

CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')


def pause(a=1.5, b=4.0):
    time.sleep(random.uniform(a, b))


def scroll(page, times=3):
    for _ in range(times):
        page.mouse.wheel(0, random.randint(280, 650))
        pause(0.9, 2.0)


def captcha_hit(page):
    try:
        u = (page.url or "").lower()
        if any(k in u for k in ("verify", "captcha", "secsdk", "challenge")):
            return True
        t = page.title() or ""
        if "验证码" in t or "安全验证" in t:
            return True
        for sel in CAPTCHA_SELECTORS:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
    except Exception:
        pass
    return False


def grab_profile(page):
    """抓主页关键信息 + 最近作品标题。"""
    out = {"url": page.url, "captcha": captcha_hit(page), "nickname": "",
           "stats": {}, "video_titles": []}
    try:
        body = page.inner_text("body")[:6000]
    except Exception:
        body = ""
    # 昵称：页面 h1 或 title
    try:
        h1 = page.query_selector("h1")
        if h1:
            out["nickname"] = (h1.inner_text() or "").strip()[:40]
    except Exception:
        pass
    if not out["nickname"]:
        out["nickname"] = (page.title() or "").split("-")[0].strip()[:40]
    # 统计：关注/粉丝/获赞
    for key in ("关注", "粉丝", "获赞"):
        m = re.search(rf"([\d\.]+[万亿wW]?)\s*{key}", body)
        if m:
            out["stats"][key] = m.group(1)
    # 作品数
    m = re.search(r"作品\s*[\[\(]?\s*(\d{1,6})", body)
    if m:
        out["stats"]["作品"] = m.group(1)
    # 作品：等作品卡片出现，再抓 /video/<id> 链接
    try:
        page.wait_for_selector('a[href*="/video/"]', timeout=20000)
    except Exception:
        pass
    try:
        vids = page.evaluate("""() => {
            const out=[]; const seen=new Set();
            document.querySelectorAll('a[href*="/video/"]').forEach(a=>{
                const h=a.getAttribute('href')||'';
                const m=h.match(/\\/video\\/(\\d+)/);
                if(!m || seen.has(m[1])) return;
                seen.add(m[1]);
                const img=a.querySelector('img');
                out.push({ aweme_id:m[1],
                    title: (a.getAttribute('aria-label')||'').slice(0,80),
                    alt: img?(img.getAttribute('alt')||'').slice(0,80):'',
                    text: (a.innerText||'').replace(/\\n/g,' | ').slice(0,100) });
            });
            return out.slice(0,30);
        }""")
        out["videos"] = vids
        out["video_titles"] = [v["text"] or v["alt"] or v["title"] for v in vids][:20]
    except Exception as e:
        out["videos"] = []
        out["video_error"] = str(e)[:80]
    return out


def extract_user_links(page, limit=10):
    """从搜索结果里提取博主：补全协议相对链接、过滤 self、保留完整 sec_uid。"""
    links, seen = [], set()
    try:
        for a in page.query_selector_all('a[href*="/user/"]'):
            href = a.get_attribute("href") or ""
            if href.startswith("//"):
                href = "https:" + href
            m = re.search(r"/user/([A-Za-z0-9_\-]+)", href)
            if not m:
                continue
            uid = m.group(1)
            if uid == "self" or uid in seen or len(uid) < 30:
                continue          # self=自己主页；短 id 是残缺链接
            seen.add(uid)
            name = (a.inner_text() or "").strip().split("\n")[0][:30]
            links.append({"sec_uid": uid,
                          "url": f"https://www.douyin.com/user/{uid}",
                          "name": name})
            if len(links) >= limit:
                break
    except Exception:
        pass
    return links


def parse_search_items(page, limit=20):
    """解析搜索结果条目文本：昵称 / 抖音号 / 获赞 / 粉丝 / 简介。"""
    out = []
    try:
        rows = page.evaluate("""() => {
            const res=[];
            document.querySelectorAll('[data-e2e="scroll-list"] > *').forEach(el=>{
                const t=(el.innerText||'').trim();
                if(t && t.length<400) res.push(t.replace(/\\n/g,'|'));
            });
            return res.slice(0,40);
        }""")
    except Exception:
        rows = []
    for t in rows:
        if "粉丝" not in t and "获赞" not in t:
            continue
        item = {"raw": t[:200]}
        m = re.match(r"(.+?)\|\|", t)
        if m:
            item["nickname"] = m.group(1).strip()[:40]
        m = re.search(r"抖音号[:：]\s*([A-Za-z0-9_\-\.]+)", t)
        if m:
            item["douyin_id"] = m.group(1)
        m = re.search(r"([\d\.]+\s*[万亿]?)\s*获赞", t)
        if m:
            item["likes"] = m.group(1).replace(" ", "")
        m = re.search(r"([\d\.]+\s*[万亿]?)\s*粉丝", t)
        if m:
            item["fans"] = m.group(1).replace(" ", "")
        out.append(item)
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", default="", help="搜索关键词；为空则用 --url")
    ap.add_argument("--url", default="", help="直接访问某个主页")
    ap.add_argument("--visits", type=int, default=3, help="访问几个博主主页")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    from patchright.sync_api import sync_playwright

    rec = {"ts": time.time(), "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
           "keyword": a.keyword, "found": [], "visited": [], "verdict": ""}

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        links = []
        if a.url:
            links = [{"url": a.url, "name": "", "sec_uid": ""}]
        else:
            q = a.keyword or "AI"
            url = f"https://www.douyin.com/search/{quote(q)}?type=user"
            print(f"[1] 搜索用户：{q}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                print(f"   加载失败 {str(e)[:70]}")
            pause(3, 5)
            if captcha_hit(page):
                rec["verdict"] = "captcha_on_search"
                print("   ⚠ 搜索页出现验证码")
            scroll(page, 2)
            links = extract_user_links(page, limit=a.visits)
            rec["search_items"] = parse_search_items(page)
            print(f"   提取到 {len(links)} 个博主")
            rec["found"] = links

        for i, l in enumerate(links[:a.visits], 1):
            print(f"[2.{i}] 访问 {l.get('name') or l['url'][-12:]}")
            try:
                page.goto(l["url"], wait_until="domcontentloaded", timeout=60000)
                pause(2.5, 4.5)
                scroll(page, 2)
                info = grab_profile(page)
                info["name"] = l.get("name")
                rec["visited"].append(info)
                print(f"      昵称={info['nickname']} 统计={info['stats']} "
                      f"作品标题={len(info['video_titles'])} 验证={info['captcha']}")
            except Exception as e:
                rec["visited"].append({"url": l["url"], "error": str(e)[:80]})
                print(f"      失败 {str(e)[:60]}")
            pause(5, 10)   # 主页之间长间隔

        ctx.close()

    caps = [v for v in rec["visited"] if v.get("captcha")]
    if rec["verdict"]:
        pass
    elif caps or not rec["visited"]:
        rec["verdict"] = "captcha_or_empty"
    else:
        rec["verdict"] = "ok"
    out = DATA / f"probe-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[结果] verdict={rec['verdict']}  发现={len(rec['found'])} "
          f"访问={len(rec['visited'])} 验证码={len(caps)}")
    print(f"[输出] {out}")


if __name__ == "__main__":
    main()

