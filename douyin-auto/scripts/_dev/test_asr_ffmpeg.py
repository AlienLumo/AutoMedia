import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT
os.environ.setdefault("HF_HOME", str(PROJECT / "runtime" / "models" / "huggingface"))
# -*- coding: utf-8 -*-
"""验证 ASR：用 ffmpeg 解码（绕开 PyAV 版本不兼容），GPU 推理。"""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

RUNTIME = PROJECT / "runtime"
FFMPEG = RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg" / "binaries" / "ffmpeg-win-x86_64-v7.1.exe"
WAV = PROJECT / "data" / "asr-test" / "sample.wav"
SR = 16000


def load_audio_ffmpeg(path, sr=SR):
    """用 ffmpeg 把任意音视频解码成 16kHz 单声道 float32 numpy。"""
    cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-i", str(path),
           "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(sr), "-"]
    out = subprocess.run(cmd, capture_output=True, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {out.stderr.decode('utf-8', 'ignore')[:200]}")
    return np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0


print("[1] ffmpeg:", FFMPEG.exists())
audio = load_audio_ffmpeg(WAV)
print(f"    解码得到 {len(audio)} 采样点 = {len(audio)/SR:.1f}s")

from faster_whisper import WhisperModel

for device, compute, size in (
        ("cuda", "int8_float16", "small"),
        ("cpu", "int8", "small")):
    print(f"\n[2] device={device} compute={compute} model={size}")
    try:
        t0 = time.time()
        model = WhisperModel(size, device=device, compute_type=compute)
        load_s = time.time() - t0
        t1 = time.time()
        segments, info = model.transcribe(audio, language="zh", beam_size=5,
                                          vad_filter=True)
        text = "".join(s.text for s in segments)
        infer_s = time.time() - t1
        dur = len(audio) / SR
        print(f"    ✅ 加载 {load_s:.1f}s  推理 {infer_s:.2f}s  "
              f"音频 {dur:.1f}s  → {dur/max(infer_s,0.01):.1f}x 实时")
        print(f"    语言={info.language}({info.language_probability:.2f})")
        print(f"    识别: {text[:150]!r}")
        if text.strip():
            print("    → GPU 链路可用 ✅")
            break
    except Exception as e:
        print(f"    ❌ {type(e).__name__}: {str(e)[:200]}")


