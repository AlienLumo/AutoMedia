import os
from _paths import PROJECT, SKILL
os.environ.setdefault("HF_HOME", str(PROJECT / "runtime" / "models" / "huggingface"))
# -*- coding: utf-8 -*-
"""probe_creator_type.py — 采集前判断博主是「口播型」还是「视觉展示型」。

原理：采样 1 个作品的前 60 秒音频跑 ASR，算「字/秒」。
  字/秒 ≥1.5 → 口播型（正常全量采字幕）
  0.8-1.5   → 混合型
  <0.8      → 视觉型（建议只采元数据+评论+封面）

成本：2 次页面访问 + 1 个 60 秒音频片段 + 10 秒 ASR ≈ 40 秒/博主
（全量采集一个博主约 60 分钟，探测只占 1%）

用法：
  python probe_creator_type.py --url "https://www.douyin.com/user/MS4w..."
  python probe_creator_type.py --url "<主页>" --profile "<profile2>"   # 双账号时
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from pathlib import Path

RUNTIME = PROJECT / "runtime"
CHROME = RUNTIME / "browsers" / "chromium-1208" / "chrome-win64" / "chrome.exe"
FFMPEG = (RUNTIME / "python" / "Lib" / "site-packages" / "imageio_ffmpeg"
          / "binaries" / "ffmpeg-win-x86_64-v7.1.exe")
PROFILE_DEFAULT = PROJECT / "data" / "social" / "douyin-verify-profile"
OUT = SKILL / "config" / "creator_types.json"
CAPTCHA_SELECTORS = ('iframe[src*="captcha"]', 'div[id*="captcha"]',
                     '#captcha_container', 'div[class*="vc-captcha"]')


def pause(a=1.2, b=3.0):
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


class Cap:
    def __init__(self, page):
        self.detail = None
        self._page = page
        page.on("response", self._on)

    def _on(self, r):
        try:
            if "/aweme/detail/" in r.url:
                self.detail = r.json()
        except Exception:
            pass

    def close(self):
        try:
            self._page.remove_listener("response", self._on)
        except Exception:
            pass


def fetch_audio(url, dest, seconds=60):
    """只下载前 N 秒音频（ffmpeg 对远程 URL 发 range 请求）。"""
    cmd = [str(FFMPEG), "-nostdin", "-v", "error", "-y",
           "-headers", "Referer: https://www.douyin.com/\r\nUser-Agent: Mozilla/5.0\r\n",
           "-t", str(seconds), "-i", url,
           "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(dest)]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    return dest.exists() and dest.stat().st_size > 5000, r.stderr.decode("utf-8", "ignore")[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--profile", default="")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()

    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from patchright.sync_api import sync_playwright

    prof = Path(a.profile) if a.profile else PROFILE_DEFAULT
    tmp = PROJECT / "data" / "_probe_tmp"
    tmp.mkdir(parents=True, exist_ok=True)

    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(prof), executable_path=str(CHROME),
            headless=a.headless, viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print(f"[1] 打开主页 {a.url}", flush=True)
        page.goto(a.url, wait_until="domcontentloaded", timeout=90000)
        pause(3, 5)
        if captcha_hit(page):
            print("  ⚠ 主页验证码，终止", flush=True)
            ctx.close()
            return 2

        # 拿作品列表（取中间位置的一个，避免置顶/最新偏向）
        try:
            page.wait_for_selector('a[href*="/video/"]', timeout=25000)
        except Exception:
            pass
        page.mouse.wheel(0, 800)
        pause(1.5, 2.5)
        vids = page.evaluate("""() => {
            const seen=new Set(); const out=[];
            document.querySelectorAll('a[href*="/video/"]').forEach(a=>{
                const m=(a.getAttribute('href')||'').match(/\\/video\\/(\\d+)/);
                if(m && !seen.has(m[1])){ seen.add(m[1]); out.push(m[1]); }
            });
            return out;
        }""")
        if not vids:
            print("  ⚠ 没找到作品", flush=True)
            ctx.close()
            return 3
        pick = vids[len(vids) // 2]
        print(f"   作品 {len(vids)} 个，采样中间一个 {pick}", flush=True)

        print(f"[2] 打开作品页拿时长/媒体地址", flush=True)
        cap = Cap(page)
        page.goto(f"https://www.douyin.com/video/{pick}",
                  wait_until="domcontentloaded", timeout=90000)
        pause(3, 5)
        if not cap.detail:
            pause(3, 5)
        aw = ((cap.detail or {}).get("aweme_detail")) or {}
        dur = ((aw.get("video") or {}).get("duration") or 0) / 1000
        desc = (aw.get("desc") or "")[:60]
        urls = (((aw.get("video") or {}).get("play_addr") or {}).get("url_list")) or []
        cap.close()
        print(f"   时长 {dur:.0f}s  文案: {desc}", flush=True)

        if not urls:
            print("  ⚠ 没拿到 play_url", flush=True)
            ctx.close()
            return 4

        print(f"[3] 下载前 {a.seconds} 秒音频", flush=True)
        wav = tmp / f"{pick}.wav"
        ok, err = False, ""
        for u in urls[:2]:
            ok, err = fetch_audio(u, wav, a.seconds)
            if ok:
                break
        if not ok:
            print(f"  ⚠ 音频下载失败: {err}", flush=True)
            ctx.close()
            return 5
        ctx.close()

    print("[4] ASR 转写", flush=True)
    t0 = time.time()
    segs, _ = model.transcribe(str(wav), language="zh", beam_size=5, vad_filter=True)
    text = "".join(s.text for s in segs)
    chars = len(re.sub(r"\s", "", text))
    used = min(a.seconds, dur) if dur else a.seconds
    cps = chars / used if used else 0
    if cps >= 1.5:
        verdict = "talk"
    elif cps >= 0.8:
        verdict = "mixed"
    else:
        verdict = "visual"

    result = {"url": a.url, "aweme_id": pick, "duration": round(dur, 1),
              "desc": desc, "chars": chars, "used_sec": round(used, 1),
              "chars_per_sec": round(cps, 2), "verdict": verdict,
              "advice": {"talk": "正常全量采集（含字幕）",
                         "mixed": "正常采集，标记混合型",
                         "visual": "只采元数据+评论+封面，跳过全量ASR"}[verdict],
              "ts": time.time()}
    print(f"\n=== 判定: {verdict} ===")
    print(f"  采样 {used:.0f}s 音频，识别 {chars} 字，字/秒 = {cps:.2f}")
    print(f"  建议: {result['advice']}")
    print(f"  ASR 耗时 {time.time()-t0:.1f}s")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    data[a.url] = result
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  已记录 → {OUT}")
    wav.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)


