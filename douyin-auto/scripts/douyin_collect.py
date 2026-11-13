#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from _paths import PROJECT, DATA
os.environ.setdefault("HF_HOME", str(PROJECT / "runtime" / "models" / "huggingface"))
"""douyin_collect.py — 单账号按需采集（接口拦截版）。

选片：置顶视频计入「播放量排名」，置顶+播放量排名合计 10 个；
      另取最新 5 个；去重后最多 15 个。
采集：文案/作者/点赞/评论数/收藏/分享/时长/封面 + 评论 + 视频(可选) + 中文字幕(ASR)。
数据来源：拦截抖音 web 的 /aweme/detail/ 与 /comment/list/ 接口，比 DOM 抓取可靠。

用法：
  python douyin_collect.py --url "<主页链接>"
  python douyin_collect.py --url "<主页链接>" --save-video yes
  python douyin_collect.py --url "<主页链接>" --save-video no --top-play 10 --latest 5
"""
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RUNTIME = PROJECT / "runtime"
PROFILE = PROJECT / "data" / "social" / "douyin-verify-profile"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
FFMPEG = (RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg"
          / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")
SR = 16000
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')


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


def play_num(s):
    """把 '12.3万' / '1.2亿' / '3456' 转成 int。对日期类脏字符串返回 0。"""
    if s is None:
        return 0
    s = str(s).strip().lower().replace(" ", "")
    # 排除日期形态（2024.09.01 / 2024-09-01），否则会被当成播放量
    if re.match(r"^\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}", s):
        return 0
    m = re.match(r"(\d+(?:\.\d+)?)\s*([万亿wWkK]?)", s)
    if not m:
        return 0
    try:
        v = float(m.group(1))
    except (TypeError, ValueError):
        return 0
    return int(v * {"万": 10000, "w": 10000, "亿": 1e8, "k": 1000}.get(m.group(2), 1))


def srt_time(sec):
    ms = int(round(float(sec) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def safe_name(s, n=50):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return (s.rstrip(". ")[:n].rstrip(". ").strip()) or "untitled"


_CC = None


def to_simplified(s):
    """Whisper 中文常输出繁体，统一转简体。"""
    global _CC
    if not s:
        return s
    try:
        if _CC is None:
            from opencc import OpenCC
            _CC = OpenCC("t2s")
        return _CC.convert(s)
    except Exception:
        return s


def list_works(page, rounds=3):
    """主页作品卡片：aweme_id / 是否置顶 / 卡片文本（含播放量）。

    rounds 控制滚动轮数：滚得越多，能加载到越早的历史作品。
    """
    try:
        page.wait_for_selector('a[href*="/video/"]', timeout=25000)
    except Exception:
        pass
    for _ in range(max(1, rounds)):
        page.mouse.wheel(0, random.randint(700, 1100))
        pause(1.2, 2.2)
    return page.evaluate("""() => {
        const res=[]; const seen=new Set();
        document.querySelectorAll('a[href*="/video/"]').forEach(a=>{
            const h=a.getAttribute('href')||'';
            const m=h.match(/\\/video\\/(\\d+)/);
            if(!m || seen.has(m[1])) return;
            seen.add(m[1]);
            const card=a.closest('li')||a.parentElement;
            const ct=card?(card.innerText||''):'';
            const img=a.querySelector('img');
            res.push({aweme_id:m[1],
                      alt:img?(img.getAttribute('alt')||''):'',
                      inner:(a.innerText||'').replace(/\\n/g,' ').slice(0,150),
                      card_text:ct.replace(/\\n/g,'|').slice(0,200),
                      pinned:/置顶/.test(ct)||/置顶/.test(a.innerText||'')});
        });
        return res;
    }""")


class PageCapture:
    """拦截 /aweme/detail/ 与 /comment/list/ 响应。"""

    def __init__(self, page):
        self.detail = None
        self.comments = []
        self.comment_total = 0
        self._page = page
        page.on("response", self._on)

    def _on(self, r):
        try:
            u = r.url
            if "/aweme/detail/" in u:
                self.detail = r.json()
            elif "/comment/list/" in u:
                j = r.json()
                self.comments.extend(j.get("comments") or [])
                self.comment_total = j.get("total") or self.comment_total
        except Exception:
            pass

    def close(self):
        try:
            self._page.remove_listener("response", self._on)
        except Exception:
            pass


def parse_detail(cap):
    aw = ((cap.detail or {}).get("aweme_detail")) or {}
    st = aw.get("statistics") or {}
    v = aw.get("video") or {}
    author = aw.get("author") or {}
    cover = (((v.get("cover") or {}).get("url_list")) or [""])[0]
    ct = aw.get("create_time")
    return {
        "aweme_id": aw.get("aweme_id"),
        "desc": (aw.get("desc") or "")[:800],
        "author": author.get("nickname"),
        "author_sec_uid": author.get("sec_uid"),
        "author_fans": author.get("follower_count"),
        "author_signature": (author.get("signature") or "")[:300],
        "author_total_favorited": author.get("total_favorited"),
        "publish": datetime.fromtimestamp(ct).strftime("%Y-%m-%d %H:%M") if ct else "",
        "duration_ms": v.get("duration"),
        "digg_count": st.get("digg_count"),
        "comment_count": st.get("comment_count"),
        "collect_count": st.get("collect_count"),
        "share_count": st.get("share_count"),
        "play_count": st.get("play_count"),
        "cover": cover,
        "play_urls": ((v.get("play_addr") or {}).get("url_list")) or [],
        "music": (aw.get("music") or {}).get("title"),
        "is_pinned": bool(aw.get("is_top")),
    }


def parse_comments(cap, limit=20):
    out = []
    for c in cap.comments[:limit]:
        ct = c.get("create_time")
        out.append({
            "cid": c.get("cid"),
            "text": (c.get("text") or "")[:500],
            "digg_count": c.get("digg_count"),
            "create_time": datetime.fromtimestamp(ct).strftime("%Y-%m-%d") if ct else "",
            "user": ((c.get("user") or {}).get("nickname")),
            "reply_total": c.get("reply_comment_total"),
        })
    return out


def download(url, dest, referer="https://www.douyin.com/"):
    cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-y",
           "-headers", f"Referer: {referer}\r\nUser-Agent: Mozilla/5.0\r\n",
           "-i", url, "-c", "copy", str(dest)]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=900)
    except Exception as e:
        return False, str(e)[:100]
    ok = dest.exists() and dest.stat().st_size > 10000
    return ok, ("" if ok else r.stderr.decode("utf-8", "ignore")[:140])


def ffmpeg_duration(path):
    try:
        r = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, timeout=60)
        m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr.decode("utf-8", "ignore"))
        if m:
            return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    except Exception:
        pass
    return 0


def load_audio(path, sr=SR):
    import numpy as np
    cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-i", str(path),
           "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(sr), "-"]
    r = subprocess.run(cmd, capture_output=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore")[:200])
    return np.frombuffer(r.stdout, dtype=np.int16).astype("float32") / 32768.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--top-play", type=int, default=10, dest="top_play")
    ap.add_argument("--latest", type=int, default=5)
    ap.add_argument("--save-video", default="auto", choices=["auto", "yes", "no", "asr"],
                    dest="save_video",
                    help="auto=短小才存; yes=全存; no=不存且不转写; asr=下完转写后删视频")
    ap.add_argument("--comments", type=int, default=20)
    ap.add_argument("--asr-model", default="large-v3", dest="asr_model")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--max-video-mb", type=float, default=80, dest="max_mb")
    ap.add_argument("--max-video-sec", type=int, default=180, dest="max_sec")
    ap.add_argument("--gap", type=float, default=25, help="作品间最小间隔秒")
    ap.add_argument("--mode", default="batch", choices=["batch", "next"],
                    help="batch=置顶+播放Top10+最新5；next=接着上次往更早采")
    ap.add_argument("--count", type=int, default=15, help="next 模式本批条数")
    ap.add_argument("--scroll", type=int, default=3,
                    help="主页滚动轮数（深历史建议 8-15）")
    ap.add_argument("--profile", default="",
                    help="浏览器 profile 目录（双账号并行时用不同目录）")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from patchright.sync_api import sync_playwright

    outroot = Path(a.outdir) if a.outdir else DATA / "douyin"
    outroot.mkdir(parents=True, exist_ok=True)
    asr_model = None

    def get_asr():
        nonlocal asr_model
        if asr_model is None:
            from faster_whisper import WhisperModel
            print("      加载 ASR 模型…")
            asr_model = WhisperModel(a.asr_model, device="cuda", compute_type="int8_float16")
        return asr_model

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(Path(a.profile) if a.profile else PROFILE),
            executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        m_uid = re.search(r"/user/([A-Za-z0-9_\-]{20,})", a.url)
        target_uid = m_uid.group(1) if m_uid else None
        print(f"[1] 打开主页 {a.url}")
        if target_uid:
            print(f"   目标 sec_uid: {target_uid[:24]}…")
        page.goto(a.url, wait_until="domcontentloaded", timeout=90000)
        pause(3, 5)
        if captcha_hit(page):
            print("   ⚠ 主页出现验证码，中止")
            ctx.close()
            return 2

        works = list_works(page, rounds=a.scroll)
        print(f"   发现作品 {len(works)} 个")
        if not works:
            ctx.close()
            return 3

        try:
            body = page.inner_text("body")[:3000]
        except Exception:
            body = ""
        nickname = (page.title() or "").split("-")[0].strip()
        nickname = re.sub(r"的抖音$", "", nickname).strip()[:30]  # 页面标题常带「的抖音」后缀

        m = re.search(r"([\d\.]+\s*[万亿]?)\s*粉丝", body)
        fans = play_num(m.group(1)) if m else 0
        fans_tag = f"{fans/10000:.1f}万" if fans >= 10000 else str(fans)
        nick_key = safe_name(nickname, 30)

        def _norm(s):
            return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", s)

        acct_dir = None
        nk = _norm(nick_key)
        for cand in sorted(outroot.iterdir(), key=lambda p: -p.stat().st_mtime):
            if not cand.is_dir():
                continue
            if _norm(cand.name).startswith(nk[:4]) and nk:
                acct_dir = cand
                print(f"   复用已有目录: {cand.name}")
                break
        if acct_dir is None:
            acct_dir = outroot / f"{nick_key}_{fans_tag}"
        acct_dir.mkdir(parents=True, exist_ok=True)
        print(f"   账号: {nickname}  粉丝≈{fans}")

        for w in works:
            nums = re.findall(r"(\d+(?:\.\d+)?\s*[万亿]?)",
                              (w.get("card_text", "") + " " + w.get("inner", "")))
            w["play"] = max([play_num(x) for x in nums], default=0)

        works_order = [w["aweme_id"] for w in works]

        # 读上次的游标
        ap_path = acct_dir / "_account.json"
        prev = {}
        if ap_path.exists():
            try:
                prev = json.loads(ap_path.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        prev_collected = [x for x in (prev.get("collected") or [])]

        if a.mode == "next":
            # 找到「最后一条已采作品」在时间轴上的位置，从它之后往更早的方向取
            pos = [i for i, aid in enumerate(works_order) if aid in prev_collected]
            start = (max(pos) + 1) if pos else 0
            chosen = [w for w in works[start:]
                      if w["aweme_id"] not in prev_collected][:a.count]
            if not pos:
                print(f"   ⚠ 未找到上次采集记录，从最新开始取 {len(chosen)} 个")
            elif not chosen:
                print(f"   ✓ 已到最早（当前能加载到 {len(works)} 个作品，"
                      f"更早的需要调大 --scroll）")
                (acct_dir / "_account.json").write_text(json.dumps({
                    **prev, "works_order": works_order, "works_seen": len(works),
                    "mode": "next", "ts": time.time(),
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M")},
                    ensure_ascii=False, indent=1), encoding="utf-8")
                ctx.close()
                return 0
            print(f"   接力采集 {len(chosen)} 个（从已采 {len(prev_collected)} 个之后往更早）")
        else:
            pinned = [w for w in works if w.get("pinned")]
            rest = sorted([w for w in works if not w.get("pinned")],
                          key=lambda x: -x["play"])
            chosen = (pinned + rest)[:max(a.top_play, len(pinned))]
            ids = {w["aweme_id"] for w in chosen}
            for w in works[:a.latest]:
                if w["aweme_id"] not in ids:
                    chosen.append(w)
                    ids.add(w["aweme_id"])
            print(f"   选片 {len(chosen)} 个（置顶 {len(pinned)} + 播放Top + 最新）")

        results = []
        for i, w in enumerate(chosen, 1):
            vid = w["aweme_id"]
            vdir = acct_dir / vid
            if (vdir / "meta.json").exists() and (vdir / "transcript.zh.txt").exists():
                print(f"   [{i}/{len(chosen)}] {vid} 已完成，跳过")
                continue
            vdir.mkdir(parents=True, exist_ok=True)
            print(f"   [{i}/{len(chosen)}] {vid} 打开作品页…")
            cap = PageCapture(page)
            try:
                page.goto(f"https://www.douyin.com/video/{vid}",
                          wait_until="domcontentloaded", timeout=90000)
            except Exception as e:
                print(f"      打开失败 {str(e)[:60]}")
                cap.close()
                continue
            pause(3, 5)
            try:
                page.click("video", timeout=4000)
            except Exception:
                pass
            pause(4, 6)
            if captcha_hit(page):
                print("      ⚠ 出现验证码，停止（已完成部分已保存）")
                cap.close()
                break
            if not cap.detail:
                pause(3, 5)
            meta = parse_detail(cap)
            if not meta.get("aweme_id"):
                meta["aweme_id"] = vid
            # 校验：必须是目标账号的作品（主页滚动会混入推荐/相关视频）
            au_uid = meta.get("author_sec_uid")
            if target_uid and au_uid and au_uid != target_uid:
                print(f"      ✗ 非本账号作品（作者={meta.get('author')}），丢弃")
                cap.close()
                try:
                    vdir.rmdir()
                except OSError:
                    shutil.rmtree(vdir, ignore_errors=True)
                time.sleep(random.uniform(3, 6))
                continue
            meta["surface_play"] = w.get("play", 0)
            meta["pinned_card"] = w.get("pinned", False)
            (vdir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"      文案: {(meta['desc'] or '')[:40]!r} 赞={meta['digg_count']} "
                  f"评={meta['comment_count']} 藏={meta['collect_count']}")

            for _ in range(2):
                page.mouse.wheel(0, random.randint(600, 900))
                pause(1.5, 2.5)
            cms = parse_comments(cap, a.comments)
            with (vdir / "comments.jsonl").open("w", encoding="utf-8") as f:
                for c in cms:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            print(f"      评论 {len(cms)} 条")

            urls = meta.get("play_urls") or []
            src = None
            if urls:
                vpath = vdir / "video.mp4"
                for u in urls[:2]:
                    ok, err = download(u, vpath)
                    if ok:
                        src = vpath
                        break
                if src:
                    mb = src.stat().st_size / 1024 / 1024
                    dur = ffmpeg_duration(src)
                    keep = a.save_video == "yes"
                    if a.save_video == "auto":
                        keep = not (mb > a.max_mb or (dur and dur > a.max_sec))
                    if keep:
                        print(f"      视频保存 {mb:.1f}MB {dur}s")
                    elif a.save_video == "no":
                        print(f"      视频 {mb:.1f}MB {dur}s（按参数 --save-video no 不保存）")
                    elif a.save_video == "asr":
                        print(f"      视频 {mb:.1f}MB {dur}s（asr 模式：转写后删除）")
                    else:
                        print(f"      视频 {mb:.1f}MB/{dur}s 超 auto 阈值"
                              f"（{a.max_mb}MB/{a.max_sec}s）→ 只留字幕")
            if src:
                try:
                    print("      ASR 转写中…")
                    audio = load_audio(src)
                    model = get_asr()
                    t0 = time.time()
                    segs, _info = model.transcribe(audio, language="zh",
                                                   beam_size=5, vad_filter=True,
                                                   condition_on_previous_text=False)
                    rows = [(s.start, s.end, to_simplified(s.text)) for s in segs]
                    (vdir / "transcript.zh.srt").write_text("\n".join(
                        f"{k}\n{srt_time(st)} --> {srt_time(en)}\n{t.strip()}\n"
                        for k, (st, en, t) in enumerate(rows, 1)), encoding="utf-8")
                    (vdir / "transcript.zh.txt").write_text(
                        "\n".join(t for _, _, t in rows), encoding="utf-8")
                    print(f"      字幕 {len(rows)} 段（{time.time()-t0:.0f}s）")
                    if a.save_video != "yes":
                        src.unlink(missing_ok=True)
                except Exception as e:
                    print(f"      ASR 失败: {type(e).__name__}: {str(e)[:100]}")
            cap.close()
            results.append(vid)
            time.sleep(random.uniform(a.gap, a.gap * 1.6))

        # 累积已采列表（跨批次保留），并记录游标
        all_collected = list(dict.fromkeys(prev_collected + results))
        cursor_last = None
        for aid in works_order:
            if aid in all_collected:
                cursor_last = aid
        # 优先用 detail 接口的 author_fans（页面文本解析常不准）
        fans_final = fans
        for _v in sorted(acct_dir.iterdir()):
            _mp = _v / "meta.json"
            if _mp.exists():
                try:
                    _m = json.loads(_mp.read_text(encoding="utf-8"))
                    if _m.get("author_fans") and (
                            not target_uid or _m.get("author_sec_uid") == target_uid):
                        fans_final = _m["author_fans"]
                        break
                except Exception:
                    pass
        (acct_dir / "_account.json").write_text(json.dumps({
            "url": a.url, "nickname": nickname, "fans": fans_final,
            "works_found": len(works), "collected": all_collected,
            "works_order": works_order, "works_seen": len(works),
            "cursor_last": cursor_last, "mode": a.mode,
            "ts": time.time(), "time": datetime.now().strftime("%Y-%m-%d %H:%M")},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[完成] {len(results)} 个作品 → {acct_dir}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)


