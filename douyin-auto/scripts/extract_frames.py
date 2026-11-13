# -*- coding: utf-8 -*-
"""对「视觉型」视频抽关键帧，供视觉分析/OCR 使用。

用法：
  python extract_frames.py --account "米小小手工_103" --limit 1 --frames 4
输出：<作品目录>_frames/frame_01.jpg ...
"""
import argparse
import json
import subprocess
from pathlib import Path
from _paths import PROJECT, DATA

RUNTIME = PROJECT / "runtime"
FFMPEG = (RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg"
          / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")
BASE = DATA / "douyin"


def probe_duration(path):
    r = subprocess.run([str(FFMPEG), "-i", str(path)], capture_output=True, timeout=60)
    import re
    m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr.decode("utf-8", "ignore"))
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="")
    ap.add_argument("--limit", type=int, default=1)
    ap.add_argument("--frames", type=int, default=4)
    a = ap.parse_args()

    accts = [BASE / a.account] if a.account else \
        [d for d in BASE.iterdir() if d.is_dir()]
    done = 0
    for acct in accts:
        if not acct.is_dir():
            continue
        for vdir in acct.iterdir():
            if not vdir.is_dir():
                continue
            mp = vdir / "meta.json"
            if not mp.exists():
                continue
            m = json.loads(mp.read_text(encoding="utf-8"))
            desc = (m.get("desc") or "")[:40]
            # 只有临时下载的视频才会存在；否则跳过
            vids = list(vdir.glob("*.mp4"))
            if not vids:
                print(f"  [无视频文件] {vdir.name}  {desc}")
                continue
            src = vids[0]
            out_dir = vdir / "_frames"
            out_dir.mkdir(exist_ok=True)
            dur = probe_duration(src) or 30
            # 在 10%-90% 区间均匀取帧
            for i in range(a.frames):
                t = dur * (0.1 + 0.8 * i / max(1, a.frames - 1))
                out = out_dir / f"frame_{i+1:02d}.jpg"
                cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-ss", f"{t:.2f}",
                       "-i", str(src), "-frames:v", "1", "-q:v", "3", "-y", str(out)]
                subprocess.run(cmd, capture_output=True, timeout=120)
            got = len(list(out_dir.glob("*.jpg")))
            print(f"  ✅ {vdir.name}  {desc}")
            print(f"     时长 {dur}s → 抽 {got} 帧 → {out_dir}")
            done += 1
            if done >= a.limit:
                return
    if done == 0:
        print("  没有找到本地视频文件（采集时已删除）")


if __name__ == "__main__":
    main()

