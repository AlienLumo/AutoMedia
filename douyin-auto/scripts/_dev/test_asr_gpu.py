import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import PROJECT
os.environ.setdefault("HF_HOME", str(PROJECT / "runtime" / "models" / "huggingface"))
# -*- coding: utf-8 -*-
"""验证 faster-whisper 能否在 CUDA 上真实推理。

用 Windows SAPI 生成一段中文语音（没有中文语音包则退化为静音），
然后用 small 模型在 GPU 上转写，确认 cuBLAS/cuDNN 加载正常、速度正常。
"""
import os
import subprocess
import sys
import time
import wave
from pathlib import Path

# 国内下载模型走镜像
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

OUT = PROJECT / "data" / "asr-test"
OUT.mkdir(parents=True, exist_ok=True)
WAV = OUT / "sample.wav"

# 1) 生成测试音频
made = False
try:
    ps = (
        'Add-Type -AssemblyName System.Speech; '
        '$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; '
        f'$s.SetOutputToWaveFile("{WAV}"); '
        '$s.Speak("你好，这是一段用于测试的中文语音。今天天气不错，我们来测试语音识别效果。"); '
        '$s.Dispose()'
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=60)
    made = WAV.exists() and WAV.stat().st_size > 1000
    print(f"[1] SAPI 生成音频: {'OK' if made else 'FAILED'} "
          f"({WAV.stat().st_size if WAV.exists() else 0} bytes)")
except Exception as e:
    print(f"[1] SAPI 失败: {str(e)[:80]}")

if not made:
    # 退化为 2 秒静音，仅用于验证 GPU 推理链路
    with wave.open(str(WAV), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x00\x00" * 16000 * 2)
    print("[1] 已生成 2 秒静音占位音频")

# 2) 加载模型并推理
from faster_whisper import WhisperModel

for device, compute in (("cuda", "int8_float16"), ("cpu", "int8")):
    print(f"\n[2] 尝试 device={device} compute={compute} …")
    try:
        t0 = time.time()
        model = WhisperModel("small", device=device, compute_type=compute)
        load_s = time.time() - t0
        t1 = time.time()
        segments, info = model.transcribe(str(WAV), language="zh", beam_size=5)
        text = "".join(s.text for s in segments)
        infer_s = time.time() - t1
        print(f"    ✅ 加载 {load_s:.1f}s  推理 {infer_s:.2f}s  "
              f"检测语言={info.language}({info.language_probability:.2f})")
        print(f"    识别结果: {text[:120]!r}")
        print(f"    → 使用 {device} 可用")
        break
    except Exception as e:
        print(f"    ❌ {device} 失败: {type(e).__name__}: {str(e)[:150]}")

