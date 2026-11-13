#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_sub_backfill.py — 给「B站本身没有 AI 字幕」的重要视频补做本地 ASR 字幕。

背景
  深采时 B站接口返回的 subtitles 为空（实测抽查全部如此），所以这些视频
  永远不会有 subtitle.*。若内容偏口播/访谈且播放量高，就值得本地转写。

做法（零 LLM token，纯本地模型）
  playurl 取音频流 -> 下载 m4a -> ffmpeg 转 16k 单声道 wav
  -> faster-whisper(large-v3, cuda, int8_float16) -> subtitle.ai-asr.srt/.txt

断点续传
  已处理过的 bvid 记在 1AMdata/_state/sub_backfill_done.json，重跑自动跳过。

用法
  python bili_sub_backfill.py --limit 3            # 试跑 3 个
  python bili_sub_backfill.py                      # 全量（后台跑）
  python bili_sub_backfill.py --dry-run            # 只列目标不下载
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from _paths import PROJECT, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from bili_subs import Bili, read_cred, HEAD  # noqa: E402

PROJ = PROJECT
DATA = PROJ / "1AMdata" / "bilibili"
STATE_DIR = PROJ / "1AMdata" / "_state"
MISSING_FILE = STATE_DIR / "sub_missing.json"
DONE_FILE = STATE_DIR / "sub_backfill_done.json"

# 明显非口播的内容，跳过（省 ASR 时间）
SKIP_TAGS = ("音乐", "MV", "鬼畜", "特效", "混剪", "剪辑", "动画", "舞蹈", "游戏实况", "纯享")


def load_done():
    if DONE_FILE.exists():
        try:
            return set(json.loads(DONE_FILE.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_done(done):
    DONE_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")


def pick_targets(min_dur, max_dur, min_view):
    j = json.loads(MISSING_FILE.read_text(encoding="utf-8"))
    imp = j.get("important") or []
    out = []
    for m in imp:
        if m["dur"] < min_dur or m["dur"] > max_dur:
            continue
        if m["view"] < min_view:
            continue
        title = m.get("title") or ""
        if any(t in title for t in SKIP_TAGS):
            continue
        out.append(m)
    # 播放高的先做
    out.sort(key=lambda x: -x["view"])
    return out


def find_meta(up, video):
    p = DATA / up / video / "meta.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def download_audio(url, dest: Path):
    req = urllib.request.Request(url, headers=HEAD)
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
    return dest.stat().st_size


def srt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_subs(vdir: Path, segments):
    srt, txt = [], []
    for i, seg in enumerate(segments, 1):
        srt.append(f"{i}\n{srt_ts(seg.start)} --> {srt_ts(seg.end)}\n{seg.text.strip()}\n")
        txt.append(seg.text.strip())
    (vdir / "subtitle.ai-asr.srt").write_text("\n".join(srt), encoding="utf-8")
    (vdir / "subtitle.ai-asr.txt").write_text("\n".join(txt), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min-dur", type=int, default=180)
    ap.add_argument("--max-dur", type=int, default=1800)
    ap.add_argument("--min-view", type=int, default=50000)
    ap.add_argument("--model", default="large-v3")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pace", type=float, default=1.5)
    a = ap.parse_args()

    targets = pick_targets(a.min_dur, a.max_dur, a.min_view)
    done = load_done()
    targets = [t for t in targets if t["video"] not in done]
    if a.limit:
        targets = targets[: a.limit]
    total_sec = sum(t["dur"] for t in targets)
    print(f"待补目标: {len(targets)} 个, 音频总长 {total_sec/3600:.1f}h, 预计 ASR {total_sec/3600/8:.1f}h", flush=True)
    if a.dry_run:
        for t in targets[:20]:
            print(f"  {t['view']:>9} 播放  {t['dur']:>5}s  {t['up'][:30]}  {t['title'][:36]}")
        return

    from faster_whisper import WhisperModel
    import numpy as np
    print("加载模型…", flush=True)
    model = WhisperModel(a.model, device="cuda", compute_type="int8_float16")
    print("模型就绪", flush=True)

    b = Bili(pace=a.pace, cooldown=120, cookies=read_cred())
    ok = fail = 0
    t_start = time.time()
    for i, t in enumerate(targets, 1):
        meta = find_meta(t["up"], t["video"])
        if not meta:
            fail += 1
            continue
        vdir = DATA / t["up"] / t["video"]
        tmp = Path(tempfile.gettempdir()) / f"bili_{meta['bvid']}.m4a"
        wav = Path(tempfile.gettempdir()) / f"bili_{meta['bvid']}.wav"
        try:
            r = b.get("x/player/playurl", {"bvid": meta["bvid"], "cid": meta["cid"],
                                           "fnval": 16, "fourk": 0})
            dash = (r.get("data") or {}).get("dash") or {}
            audios = dash.get("audio") or []
            if not audios:
                print(f"[{i}/{len(targets)}] no audio stream: {meta['bvid']}", flush=True)
                done.add(t["video"]); save_done(done); fail += 1
                continue
            best = max(audios, key=lambda x: x.get("bandwidth") or 0)
            url = best.get("baseUrl") or best.get("base_url") or ""
            if not url:
                done.add(t["video"]); save_done(done); fail += 1
                continue
            size = download_audio(url, tmp)
            subprocess.run([ffmpeg_exe(), "-y", "-loglevel", "error", "-i", str(tmp),
                            "-ac", "1", "-ar", "16000", str(wav)],
                           check=True, timeout=600)
            # PyAV 19 移除了 faster-whisper 依赖的 metadata_errors 参数，
            # 所以自己用 ffmpeg 解码成 float32 numpy 再喂模型（抖音链路同款做法）。
            raw = subprocess.run([ffmpeg_exe(), "-loglevel", "error", "-i", str(wav),
                                  "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                                 capture_output=True, check=True, timeout=600).stdout
            audio = np.frombuffer(raw, dtype=np.float32)
            if audio.size == 0:
                raise RuntimeError("empty audio")
            segs, info = model.transcribe(audio, language="zh", vad_filter=True,
                                          beam_size=1, condition_on_previous_text=False)
            segs = list(segs)
            if not segs:
                print(f"[{i}/{len(targets)}] empty transcript: {meta['bvid']}", flush=True)
                done.add(t["video"]); save_done(done); fail += 1
                continue
            write_subs(vdir, segs)
            done.add(t["video"]); save_done(done)
            ok += 1
            el = time.time() - t_start
            print(f"[{i}/{len(targets)}] OK {meta['bvid']} {t['dur']}s audio {size//1024}KB "
                  f"segs={len(segs)} elapsed={el/60:.1f}m", flush=True)
        except Exception as e:
            print(f"[{i}/{len(targets)}] FAIL {meta.get('bvid')}: {type(e).__name__}: {e}", flush=True)
            fail += 1
        finally:
            for p in (tmp, wav):
                try:
                    p.unlink()
                except Exception:
                    pass
    print(f"\n完成: ok={ok} fail={fail} 用时 {(time.time()-t_start)/60:.1f} 分钟", flush=True)


if __name__ == "__main__":
    main()
