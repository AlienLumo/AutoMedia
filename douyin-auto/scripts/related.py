# -*- coding: utf-8 -*-
"""related.py — 给一个视频链接，挖「相关推荐」里的视频与博主。

覆盖场景：
  ④ 给某个视频链接 → 查询相关主题内容的其他视频
  ⑤ 给某个视频链接 → 查询相关主题内容的其他博主

原理：抖音作品页会请求 `/aweme/v1/web/aweme/related/`，
      返回的 aweme_list 就是「同主题相关视频」，每条带作者信息。
      比关键词搜索更准——算法已经按内容相似度排好了。

用法：
  python related.py --url "https://v.douyin.com/xxxx/"                      # 只列相关视频
  python related.py --url "..." --min-fans 100000 --queue                  # 生成博主采集队列
  python related.py --url "..." --min-fans 100000 --queue --collect        # 生成并采集
  python related.py --url "..." --rounds 3                                 # 多打开几个相关视频再扩散
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from _paths import PROJECT, SKILL

RUNTIME = PROJECT / "runtime"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
SCRIPTS = Path(__file__).resolve().parent
CONF = SKILL / "config"
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')


def captcha_hit(page):
    try:
        u = (page.url or "").lower()
        if any(k in u for k in ("verify", "captcha", "secsdk", "challenge")):
            return True
        if "验证码" in (page.title() or ""):
            return True
        for sel in CAPTCHA_SELECTORS:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return True
    except Exception:
        pass
    return False


def fmt(n):
    n = n or 0
    return f"{n/1e4:.1f}万" if n >= 1e4 else str(n)


class Capture:
    def __init__(self, page):
        self.detail = {}
        self.related = []
        self._page = page
        page.on("response", self._on)

    def _on(self, r):
        try:
            u = r.url
            if "/aweme/detail/" in u:
                self.detail = r.json() or {}
            elif "/aweme/related/" in u:
                j = r.json() or {}
                for aw in (j.get("aweme_list") or []):
                    self.related.append(aw)
        except Exception:
            pass

    def close(self):
        try:
            self._page.remove_listener("response", self._on)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--profile", default="")
    ap.add_argument("--rounds", type=int, default=1, help="扩散轮数（打开几个相关视频再挖）")
    ap.add_argument("--min-fans", type=int, default=100000, dest="min_fans")
    ap.add_argument("--queue", action="store_true", help="生成博主采集队列文件")
    ap.add_argument("--collect", action="store_true", help="生成后直接采集")
    ap.add_argument("--top-play", type=int, default=10, dest="top_play")
    ap.add_argument("--latest", type=int, default=5)
    ap.add_argument("--gap", type=int, default=55)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    from patchright.sync_api import sync_playwright

    prof = Path(a.profile) if a.profile else PROFILE
    videos = {}          # aweme_id -> {desc, digg, author...}
    authors = {}         # sec_uid -> {...}
    seen_ids = set()

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(prof), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        cur_url = a.url
        for rd in range(max(1, a.rounds)):
            cap = Capture(page)
            print(f"\n[轮 {rd+1}/{a.rounds}] 打开 {cur_url[:80]}", flush=True)
            page.goto(cur_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(5000)
            if captcha_hit(page):
                print("  ⚠ 验证码，停止", flush=True)
                cap.close()
                break
            # 滚动触发相关推荐加载
            for _ in range(2):
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(2500)
            if not cap.related:
                page.wait_for_timeout(4000)

            seed_aw = (cap.detail.get("aweme_detail") or {})
            seed_author = (seed_aw.get("author") or {})
            print(f"  相关视频 {len(cap.related)} 条；种子作者: {seed_author.get('nickname')}",
                  flush=True)

            for aw in cap.related:
                aid = aw.get("aweme_id")
                if not aid:
                    continue
                au = aw.get("author") or {}
                st = aw.get("statistics") or {}
                if aid not in seen_ids:
                    seen_ids.add(aid)
                    videos[aid] = {
                        "aweme_id": aid,
                        "desc": (aw.get("desc") or "")[:80],
                        "digg": st.get("digg_count") or 0,
                        "duration_s": (aw.get("video") or {}).get("duration", 0) // 1000,
                        "author": au.get("nickname"),
                        "sec_uid": au.get("sec_uid"),
                    }
                sec = au.get("sec_uid")
                if sec and sec not in authors:
                    authors[sec] = {
                        "sec_uid": sec, "name": au.get("nickname"),
                        "fans": au.get("follower_count") or 0,
                        "hits": 0, "best": "",
                    }
                if sec:
                    authors[sec]["hits"] = authors[sec].get("hits", 0) + 1
                    if (st.get("digg_count") or 0) > (authors[sec].get("best_digg") or 0):
                        authors[sec]["best_digg"] = st.get("digg_count") or 0
                        authors[sec]["best"] = (aw.get("desc") or "")[:60]
            cap.close()

            # 下一轮：换一个高赞相关视频当种子（扩散）
            if rd + 1 < a.rounds:
                cand = sorted([v for v in videos.values() if v["aweme_id"] !=
                               (seed_aw.get("aweme_id"))],
                              key=lambda x: -x["digg"])
                if not cand:
                    break
                cur_url = f'https://www.douyin.com/video/{cand[0]["aweme_id"]}'
                print(f"  下一轮种子: {cand[0]['desc'][:40]}（{fmt(cand[0]['digg'])}赞）",
                      flush=True)
                time.sleep(8)

        ctx.close()

    # 输出
    print("\n" + "=" * 62)
    print(f"相关视频 {len(videos)} 条，涉及作者 {len(authors)} 个")
    print("=" * 62)
    top_v = sorted(videos.values(), key=lambda x: -x["digg"])
    print("\n相关视频 Top 10（按点赞）：")
    for v in top_v[:10]:
        print(f'  {fmt(v["digg"]):>7}  {v["author"] or "?"}：{v["desc"][:38]}')

    big = sorted([x for x in authors.values() if (x.get("fans") or 0) >= a.min_fans],
                 key=lambda x: -(x.get("fans") or 0))
    print(f'\n≥{fmt(a.min_fans)}粉 作者 {len(big)} 个：')
    for x in big[:20]:
        print(f'  {fmt(x["fans"]):>7}  命中{x["hits"]}条  {x["name"]}')

    # 落盘
    CONF.mkdir(parents=True, exist_ok=True)
    out_json = CONF / "related_result.json"
    seed_id = (videos and next(iter(videos))) or "unknown"
    out_json.write_text(json.dumps(
        {"seed_url": a.url, "videos": top_v, "authors": big,
         "min_fans": a.min_fans}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n结果: {out_json}")

    if a.queue or a.collect:
        qf = CONF / "queue_related.txt"
        qf.write_text("\n".join(f'https://www.douyin.com/user/{x["sec_uid"]}'
                                for x in big) + "\n", encoding="utf-8")
        print(f"队列: {qf}  ({len(big)} 个博主)")

    if a.collect:
        print("\n开始采集（每号 top%d+latest%d）…" % (a.top_play, a.latest), flush=True)
        py = sys.executable
        cmd = [py, str(SCRIPTS / "run_queue.ps1")] if False else None  # run_queue 是 ps1
        # 用 python 循环调 douyin_collect
        for i, x in enumerate(big, 1):
            print(f"\n[{i}/{len(big)}] {x['name']}  {fmt(x['fans'])}", flush=True)
            c = [py, str(SCRIPTS / "douyin_collect.py"),
                 "--url", f'https://www.douyin.com/user/{x["sec_uid"]}',
                 "--top-play", str(a.top_play), "--latest", str(a.latest),
                 "--comments", "20", "--save-video", "no", "--gap", str(a.gap)]
            if a.profile:
                c += ["--profile", a.profile]
            subprocess.run(c)
            time.sleep(20)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

