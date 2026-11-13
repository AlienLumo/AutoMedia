#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from _paths import PROJECT
os.environ.setdefault("HF_HOME", str(PROJECT / "runtime" / "models" / "huggingface"))
"""collect_one_video.py — 单条作品采集（人物访谈场景）。

只采一个 aweme_id：文案/作者/互动数/评论 + 视频 → ASR 逐字稿 → 删视频。
复用 douyin_collect.py 的拦截与 ASR 实现，避免另起一套。

用法：
  python collect_one_video.py --video 7705000321369640230 --outdir "D:\\...\\1AMdata\\先锋人物\\douyin"
  python collect_one_video.py --video <id> --outdir <池> --max-min 90
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from douyin_collect import (PageCapture, parse_detail, parse_comments, download,   # noqa: E402
                            load_audio, ffmpeg_duration, to_simplified, srt_time,
                            safe_name, captcha_hit, pause, PROFILE, CHROME)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="aweme_id")
    ap.add_argument("--outdir", required=True, help="池子根目录，如 ...\\1AMdata\\先锋人物\\douyin")
    ap.add_argument("--comments", type=int, default=20)
    ap.add_argument("--asr-model", default="large-v3", dest="asr_model")
    ap.add_argument("--max-min", type=float, default=90, dest="max_min",
                    help="超过该时长不做 ASR（防跑飞）")
    ap.add_argument("--keep-video", action="store_true", help="保留 mp4")
    ap.add_argument("--profile", default="")
    a = ap.parse_args()

    outroot = Path(a.outdir)
    outroot.mkdir(parents=True, exist_ok=True)

    from patchright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(Path(a.profile) if a.profile else PROFILE),
            executable_path=str(CHROME), headless=False,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print(f"[1] 打开作品页 {a.video}")
        cap = PageCapture(page)
        page.goto(f"https://www.douyin.com/video/{a.video}",
                  wait_until="domcontentloaded", timeout=90000)
        pause(3, 5)
        try:
            page.click("video", timeout=4000)
        except Exception:
            pass
        pause(4, 6)
        if captcha_hit(page):
            print("   ⚠ 出现验证码，中止")
            ctx.close()
            return 2
        if not cap.detail:
            pause(4, 6)
        meta = parse_detail(cap)
        if not meta.get("aweme_id"):
            meta["aweme_id"] = a.video
        if not meta.get("author"):
            print("   ⚠ 未拿到 detail，可能被风控")
            ctx.close()
            return 3

        nick = safe_name(meta.get("author") or "unknown", 30)
        fans = meta.get("author_fans") or 0
        tag = f"{fans/10000:.1f}万" if fans >= 10000 else str(fans)
        acct_dir = outroot / f"{nick}_{tag}"
        vdir = acct_dir / a.video
        vdir.mkdir(parents=True, exist_ok=True)
        (vdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
        print(f"   作者={meta['author']} 粉丝={fans} 时长={meta.get('duration_ms')}")
        print(f"   文案={(meta['desc'] or '')[:60]!r}")

        for _ in range(2):
            page.mouse.wheel(0, 700)
            pause(1.5, 2.5)
        cms = parse_comments(cap, a.comments)
        with (vdir / "comments.jsonl").open("w", encoding="utf-8") as f:
            for c in cms:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"   评论 {len(cms)} 条")
        cap.close()

        urls = meta.get("play_urls") or []
        vpath = vdir / "video.mp4"
        src = None
        for u in urls[:2]:
            ok, err = download(u, vpath)
            if ok:
                src = vpath
                break
            print(f"   下载失败: {err}")
        if not src:
            print("   ✗ 视频下载失败，无法转写")
            ctx.close()
            return 4

        dur = ffmpeg_duration(src)
        mb = src.stat().st_size / 1024 / 1024
        print(f"   视频 {mb:.1f}MB {dur}s")
        if dur and dur > a.max_min * 60:
            print(f"   ⚠ 超过 {a.max_min} 分钟上限，跳过 ASR")
            ctx.close()
            return 5

        from faster_whisper import WhisperModel
        print("   加载 ASR 模型…")
        model = WhisperModel(a.asr_model, device="cuda", compute_type="int8_float16")
        print("   ASR 转写中…")
        t0 = time.time()
        audio = load_audio(src)
        segs, _info = model.transcribe(audio, language="zh", beam_size=5, vad_filter=True,
                                       condition_on_previous_text=False)
        rows = [(s.start, s.end, to_simplified(s.text)) for s in segs]
        (vdir / "transcript.zh.srt").write_text("\n".join(
            f"{k}\n{srt_time(st)} --> {srt_time(en)}\n{t.strip()}\n"
            for k, (st, en, t) in enumerate(rows, 1)), encoding="utf-8")
        text = "\n".join(t for _, _, t in rows)
        (vdir / "transcript.zh.txt").write_text(text, encoding="utf-8")
        print(f"   字幕 {len(rows)} 段 / {len(text)} 字（{time.time()-t0:.0f}s）")

        if not a.keep_video:
            src.unlink(missing_ok=True)

        acc = acct_dir / "_account.json"
        prev = {}
        if acc.exists():
            try:
                prev = json.loads(acc.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        col = list(dict.fromkeys((prev.get("collected") or []) + [a.video]))
        acc.write_text(json.dumps({
            "url": f"https://www.douyin.com/user/{meta.get('author_sec_uid')}",
            "nickname": meta.get("author"), "fans": fans,
            "collected": col, "mode": "single",
            "ts": time.time(), "time": datetime.now().strftime("%Y-%m-%d %H:%M")},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[完成] → {vdir}")
        ctx.close()
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

