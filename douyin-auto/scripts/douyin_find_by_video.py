# -*- coding: utf-8 -*-
"""douyin_find_by_video.py — 通过「视频内容搜索」反查博主（比按名字搜准得多）。

原理：打开抖音搜索页 type=video，拦截 `/aweme/v1/web/search/item/` 接口，
      从返回的 aweme 列表里提取 author（昵称/sec_uid/粉丝数）与视频数据，
      按作者聚合，统计「命中几个视频/几个关键词/总赞」，再按粉丝过滤。

覆盖领域（用户指定）：创业 / 创客 / 名人访谈 / 科技前沿 / 前沿资讯 / 科技商业 / 科技科普

安全：每关键词间隔 N 秒（默认 420s=7分钟），触发验证码立即停止并保留进度。

用法：
  python douyin_find_by_video.py                       # 全部领域
  python douyin_find_by_video.py --themes 创业,科技前沿
  python douyin_find_by_video.py --gap 300 --min-fans 100000
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
STATE = OUT_DIR / "video_search_state.json"
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')

THEMES = {
    "科技创客": [
        "AI Agent", "智能体搭建", "本地部署大模型", "AI工作流", "自制AI",
        "自制机器人", "DIY机器人", "开源机器人", "机器狗", "机械臂",
        "电路设计", "PCB设计", "单片机", "STM32", "树莓派",
        "Arduino", "ESP32", "嵌入式开发", "开源硬件", "自制硬件",
    ],
    "创业": ["创业", "一人公司", "独立创业", "副业", "创业项目", "小生意", "商业思维",
             "创业故事", "实体店创业"],
    "创客": ["创客", "DIY", "手工制作", "发明", "硬件开发", "3D打印", "开源硬件",
             "电子制作", "改造"],
    "名人访谈": ["访谈", "创业者访谈", "深度对话", "商业访谈", "大佬访谈", "人物专访",
                 "对话创始人"],
    "科技前沿": ["科技前沿", "前沿科技", "黑科技", "未来科技", "新技术", "技术突破",
                 "科技创新"],
    "前沿资讯": ["科技资讯", "AI资讯", "行业资讯", "科技新闻", "发布会", "新品发布",
                 "科技动态"],
    "科技商业": ["科技商业", "商业分析", "公司分析", "行业分析", "产业链", "商业模式",
                 "科技公司"],
    "科技科普": ["科技科普", "科普", "硬核科普", "原理", "技术解读", "知识科普",
                 "科学知识"],
}


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


class SearchCapture:
    """拦截抖音视频搜索接口。"""

    def __init__(self, page):
        self.items = []
        self._page = page
        page.on("response", self._on)

    def _on(self, r):
        try:
            if "/aweme/v1/web/search/item/" in r.url:
                j = r.json()
                for d in (j.get("data") or []):
                    aw = d.get("aweme_info")
                    if aw:
                        self.items.append(aw)
        except Exception:
            pass

    def close(self):
        try:
            self._page.remove_listener("response", self._on)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--themes", default="", help="逗号分隔，默认全部")
    ap.add_argument("--gap", type=int, default=420, help="关键词间隔秒（默认 420）")
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--scroll", type=int, default=1)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    picked = [t.strip() for t in a.themes.split(",") if t.strip()] or list(THEMES)
    kws = []
    for t in picked:
        for k in THEMES.get(t, []):
            kws.append((t, k))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            st = {}
    done = set(st.get("done_keywords") or [])
    authors = {x["sec_uid"]: x for x in (st.get("authors") or [])}

    todo = [(t, k) for t, k in kws if k not in done]
    print(f"[start] 主题 {len(picked)} 个 / 关键词 {len(todo)} 个待搜"
          f"（已完成 {len(done)}）", flush=True)

    from patchright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        for i, (theme, kw) in enumerate(todo, 1):
            url = f"https://www.douyin.com/search/{quote(kw)}?type=video"
            print(f"\n[{i}/{len(todo)}] 「{theme}」搜索视频：{kw}", flush=True)
            cap = SearchCapture(page)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                print(f"  加载失败 {str(e)[:60]}", flush=True)
                cap.close()
                continue
            pause(2, 3)
            if captcha_hit(page):
                print("  ⚠ 触发验证码，停止（进度已保存）", flush=True)
                cap.close()
                break
            # 主动等搜索接口返回（之前只等 4-5 秒，接口还没回就读，导致 0 条）
            for _ in range(25):
                if cap.items:
                    break
                page.wait_for_timeout(1000)
                if captcha_hit(page):
                    break
            for _ in range(max(1, a.scroll)):
                page.mouse.wheel(0, random.randint(500, 800))
                page.wait_for_timeout(2500)
            if not cap.items:
                print("  ⚠ 未收到搜索接口数据（可能被限流），跳过", flush=True)
                cap.close()
                done.add(kw)
                continue

            new = 0
            for aw in cap.items:
                au = aw.get("author") or {}
                uid = au.get("sec_uid")
                if not uid:
                    continue
                stats = aw.get("statistics") or {}
                digg = stats.get("digg_count") or 0
                if uid not in authors:
                    authors[uid] = {
                        "sec_uid": uid,
                        "nickname": au.get("nickname"),
                        "fans": au.get("follower_count") or 0,
                        "total_favorited": au.get("total_favorited") or 0,
                        "signature": (au.get("signature") or "").replace("\n", " ")[:150],
                        "themes": [theme],
                        "keywords": [kw],
                        "videos_hit": 1,
                        "total_likes": digg,
                        "best_video": (aw.get("desc") or "")[:80],
                        "best_likes": digg,
                        "found_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    }
                    new += 1
                else:
                    x = authors[uid]
                    if kw not in x["keywords"]:
                        x["keywords"].append(kw)
                    if theme not in x["themes"]:
                        x["themes"].append(theme)
                    x["videos_hit"] = x.get("videos_hit", 0) + 1
                    x["total_likes"] = x.get("total_likes", 0) + digg
                    if digg > x.get("best_likes", 0):
                        x["best_likes"] = digg
                        x["best_video"] = (aw.get("desc") or "")[:80]
            print(f"  视频 {len(cap.items)} 条，新增作者 {new}，累计 {len(authors)}", flush=True)
            cap.close()
            done.add(kw)

            st = {"done_keywords": sorted(done), "authors": list(authors.values()),
                  "updated": datetime.now().strftime("%Y-%m-%d %H:%M")}
            STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")

            if i < len(todo):
                wait = a.gap + random.randint(-45, 90)
                print(f"  休息 {wait}s（防风控）…", flush=True)
                time.sleep(max(60, wait))

        ctx.close()

    rows = [x for x in authors.values() if (x.get("fans") or 0) >= a.min_fans]
    rows.sort(key=lambda x: -x.get("fans", 0))
    tsv = OUT_DIR / "douyin_video_found_bloggers.tsv"
    with tsv.open("w", encoding="utf-8") as f:
        f.write("sec_uid\t昵称\t粉丝\t总获赞\t领域\t命中关键词\t命中视频数\t最高赞\t代表作\n")
        for b in rows:
            f.write(f'{b["sec_uid"]}\t{b["nickname"]}\t{b["fans"]}\t'
                    f'{b.get("total_favorited",0)}\t{",".join(b.get("themes",[]))}\t'
                    f'{",".join(b.get("keywords",[])[:5])}\t{b.get("videos_hit",0)}\t'
                    f'{b.get("best_likes",0)}\t{b.get("best_video","")}\n')
    print(f"\n[done] ≥{a.min_fans}粉的作者 {len(rows)} 个 -> {tsv}", flush=True)
    for b in rows[:25]:
        print(f'  {b["fans"]/1e4:>8.1f}万  [{",".join(b.get("themes",[]))[:10]}]  '
              f'{b["nickname"]}  命中{b.get("videos_hit",0)}条', flush=True)


if __name__ == "__main__":
    main()

