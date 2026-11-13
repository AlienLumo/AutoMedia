#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reasr_local.py — 用本地已有的 mp4 重跑 ASR，覆盖 transcript。无需浏览器。

用途：修掉 Whisper 幻觉（时间轴超出视频真实时长的那部分），
或换模型/参数重转。视频时长会与字幕末端比对，超出部分直接丢弃。

用法：
  python reasr_local.py --dir "<作品目录>"            # 找目录里的 mp4
  python reasr_local.py --video a.mp4 --dir <目录>
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from douyin_collect import (load_audio, ffmpeg_duration, to_simplified, srt_time,  # noqa: E402
                            FFMPEG)

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="作品目录（含 mp4）")
    ap.add_argument("--video", default="", help="mp4 路径，默认在 --dir 下找")
    ap.add_argument("--asr-model", default="large-v3", dest="asr_model")
    a = ap.parse_args()

    d = Path(a.dir)
    if a.video:
        src = Path(a.video)
    else:
        cands = [p for p in d.glob("*.mp4")]
        if not cands:
            print("目录里没有 mp4")
            return 2
        src = cands[0]

    dur = ffmpeg_duration(src)
    print(f"视频 {src.name} 实测 {dur}s")

    from faster_whisper import WhisperModel
    model = WhisperModel(a.asr_model, device="cuda", compute_type="int8_float16")
    audio = load_audio(src)
    segs, info = model.transcribe(audio, language="zh", beam_size=5, vad_filter=True,
                                  condition_on_previous_text=False)
    rows, dropped = [], 0
    for s in segs:
        if dur and s.start >= dur:          # 超出真实时长 → 幻觉，丢弃
            dropped += 1
            continue
        rows.append((s.start, min(s.end, dur) if dur else s.end, to_simplified(s.text)))

    (d / "transcript.zh.srt").write_text("\n".join(
        f"{k}\n{srt_time(st)} --> {srt_time(en)}\n{t.strip()}\n"
        for k, (st, en, t) in enumerate(rows, 1)), encoding="utf-8")
    text = "\n".join(t for _, _, t in rows)
    (d / "transcript.zh.txt").write_text(text, encoding="utf-8")
    print(f"重转完成：{len(rows)} 段 / {len(text)} 字；丢弃幻觉段 {dropped} 段")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
