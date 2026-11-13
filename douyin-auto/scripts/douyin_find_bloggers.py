# -*- coding: utf-8 -*-
"""douyin_find_bloggers.py — 抖音搜索 AI 相关博主（低频安全版）。

策略（防封）：
  - 每个关键词之间间隔 N 秒（默认 480s = 8 分钟）
  - 每次搜索只滚动少量（默认 2 轮）
  - 触发验证码立即停止，已采结果保留
  - 结果按粉丝量排序，去重（sec_uid）

用法：
  python douyin_find_bloggers.py --keywords "AI,人工智能,AI工具" --gap 480 --min-fans 100000
  python douyin_find_bloggers.py --keywords-file ../config/ai_keywords.txt
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
from _paths import PROJECT, SKILL

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
OUT_DIR = SKILL / "config"
STATE = OUT_DIR / "blogger_search_state.json"
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')

DEFAULT_KW = ("AI,人工智能,AI工具,大模型,AI绘画,AI视频,AI教程,AI副业,"
              "AI编程,智能体,ChatGPT,AIGC,AI数字人,AI办公,提示词")


def pause(a=1.5, b=4.0):
    time.sleep(random.uniform(a, b))


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


def num(s):
    if not s:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    m = re.match(r"([\d\.]+)\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    return int(float(m.group(1)) *
               {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))


def extract_cards(page):
    """从搜索结果页提取博主卡片：sec_uid / 昵称 / 抖音号 / 粉丝 / 获赞 / 简介。"""
    return page.evaluate("""() => {
        const res = [];
        const seen = new Set();
        // 搜索结果的每张用户卡
        document.querySelectorAll('a[href*="/user/"]').forEach(a => {
            const h = a.getAttribute('href') || '';
            const m = h.match(/\\/user\\/([A-Za-z0-9_\\-]{20,})/);
            if (!m) return;
            const uid = m[1];
            if (seen.has(uid)) return;
            seen.add(uid);
            // 向上找卡片容器（包含粉丝字样的最近祖先）
            let card = a;
            for (let i = 0; i < 6 && card; i++) {
                if (/粉丝/.test(card.innerText || '')) break;
                card = card.parentElement;
            }
            const t = card ? (card.innerText || '') : '';
            res.push({
                sec_uid: uid,
                url: 'https://www.douyin.com/user/' + uid,
                text: t.replace(/\\n/g, '|').slice(0, 400),
                link_text: (a.innerText || '').replace(/\\n/g, '|').slice(0, 100)
            });
        });
        return res;
    }""")


def parse_card(c):
    t = c.get("text") or ""
    out = {"sec_uid": c["sec_uid"], "url": c["url"], "nickname": "",
           "douyin_id": "", "fans": 0, "likes": 0, "signature": "", "raw": t[:250]}
    m = re.match(r"([^|]+)", t)
    if m:
        out["nickname"] = m.group(1).strip()[:40]
    m = re.search(r"抖音号[:：]\s*([A-Za-z0-9_\-\.]+)", t)
    if m:
        out["douyin_id"] = m.group(1)
    m = re.search(r"([\d\.]+\s*[万亿]?)\s*获赞", t)
    if m:
        out["likes"] = num(m.group(1))
    m = re.search(r"([\d\.]+\s*[万亿]?)\s*粉丝", t)
    if m:
        out["fans"] = num(m.group(1))
    # 简介：取「粉丝」之后的部分
    m = re.search(r"粉丝\s*\|*\s*(.+)$", t)
    if m:
        out["signature"] = m.group(1).replace("|", " ").strip()[:150]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default=DEFAULT_KW)
    ap.add_argument("--keywords-file", default="", dest="kwfile")
    ap.add_argument("--gap", type=int, default=480, help="关键词间隔秒（默认 480=8分钟）")
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--scroll", type=int, default=2)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    kws = [k.strip() for k in a.keywords.split(",") if k.strip()]
    if a.kwfile and Path(a.kwfile).exists():
        kws += [l.strip() for l in Path(a.kwfile).read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            st = {}
    done_kw = set(st.get("done_keywords") or [])
    bloggers = {b["sec_uid"]: b for b in (st.get("bloggers") or [])}

    from patchright.sync_api import sync_playwright

    todo = [k for k in kws if k not in done_kw]
    print(f"[start] 关键词 {len(todo)} 个待搜（已完成 {len(done_kw)}）", flush=True)

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, kw in enumerate(todo, 1):
            url = f"https://www.douyin.com/search/{quote(kw)}?type=user"
            print(f"\n[{i}/{len(todo)}] 搜索「{kw}」", flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                print(f"  加载失败 {str(e)[:60]}", flush=True)
                continue
            pause(3, 5)
            if captcha_hit(page):
                print("  ⚠ 触发验证码，停止（进度已保存）", flush=True)
                break
            for _ in range(max(1, a.scroll)):
                page.mouse.wheel(0, random.randint(600, 900))
                pause(1.5, 2.5)
            if captcha_hit(page):
                print("  ⚠ 滚动后触发验证码，停止", flush=True)
                break

            cards = extract_cards(page)
            new = 0
            for c in cards:
                b = parse_card(c)
                if not b["sec_uid"]:
                    continue
                if b["fans"] and b["fans"] < a.min_fans:
                    continue
                if b["sec_uid"] not in bloggers:
                    b["found_by"] = [kw]
                    b["found_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    bloggers[b["sec_uid"]] = b
                    new += 1
                else:
                    if kw not in bloggers[b["sec_uid"]].get("found_by", []):
                        bloggers[b["sec_uid"]].setdefault("found_by", []).append(kw)
            print(f"  卡片 {len(cards)}，新增 {new}，累计 {len(bloggers)}", flush=True)
            done_kw.add(kw)

            st = {"done_keywords": sorted(done_kw),
                  "bloggers": list(bloggers.values()),
                  "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
            STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")

            if i < len(todo):
                wait = a.gap + random.randint(-60, 120)
                print(f"  休息 {wait}s 再搜下一个（防风控）…", flush=True)
                time.sleep(max(60, wait))

        ctx.close()

    # 导出 TSV（按粉丝降序）
    rows = sorted(bloggers.values(), key=lambda x: -x.get("fans", 0))
    tsv = OUT_DIR / "douyin_ai_bloggers.tsv"
    with tsv.open("w", encoding="utf-8") as f:
        f.write("sec_uid\t昵称\t粉丝\t获赞\t抖音号\t被搜索词\t简介\n")
        for b in rows:
            f.write(f'{b["sec_uid"]}\t{b["nickname"]}\t{b["fans"]}\t{b["likes"]}\t'
                    f'{b.get("douyin_id","")}\t{",".join(b.get("found_by", []))}\t'
                    f'{b.get("signature","")}\n')
    print(f"\n[done] 博主 {len(rows)} 个 -> {tsv}", flush=True)
    for b in rows[:20]:
        print(f'  {b["fans"]/1e4:>8.1f}万  {b["nickname"]}', flush=True)


if __name__ == "__main__":
    main()

