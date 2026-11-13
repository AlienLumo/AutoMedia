#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""capture_visuals.py — 为 1信息源/<日期> 各事件抓取视觉素材：
  截图/  整页长图、标题区、滚动分镜
  录屏/  页面滚动视频（webm 录制，失败则用分镜拼 mp4）
  关键人物/  Wikipedia 头像（CC 授权，附来源）

用法：runtime\\python\\python.exe capture_visuals.py --only 01_anthropic-ipo
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir, CHROME, FFMPEG

BASE = day_dir()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
VW, VH = 1440, 900

PEOPLE = [
    ("黄仁勋_Jensen_Huang", "Jensen_Huang"),
    ("达里奥·阿莫代伊_Dario_Amodei", "Dario_Amodei"),
    ("萨姆·奥尔特曼_Sam_Altman", "Sam_Altman"),
    ("桑达尔·皮查伊_Sundar_Pichai", "Sundar_Pichai"),
    ("埃隆·马斯克_Elon_Musk", "Elon_Musk"),
]


def is_cn(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        host = ""
    cn_hosts = ("ithome.com", "tmtpost.com", "eastmoney.com", "36kr.com",
                "leiphone.com", "geekpark.net", "cnstock.com", "stcn.com",
                "nbd.com.cn", "yicai.com", "jiemian.com", "thepaper.cn")
    return host.endswith(".cn") or any(h in host for h in cn_hosts)


def pick_urls(slug):
    d = BASE / slug
    links = json.loads((d / "links.json").read_text(encoding="utf-8"))
    ok = [m for m in links if m.get("chars", 0) > 400]
    cn = sorted([m for m in ok if is_cn(m["url"])], key=lambda m: -m["chars"])
    en = sorted([m for m in ok if not is_cn(m["url"])], key=lambda m: -m["chars"])
    urls = []
    for m in cn[:2]:
        urls.append(("CN_" + m["label"], m["url"]))
    if en:
        urls.append(("EN_" + en[0]["label"], en[0]["url"]))
    # 官方动态页
    for f in sorted((d / "原文").glob("官方动态_*.md")):
        head = f.read_text(encoding="utf-8", errors="replace").splitlines()[:4]
        u = next((l.split("URL:", 1)[1].strip() for l in head if "URL:" in l), "")
        if u:
            urls.append(("OFFICIAL_" + f.stem.replace("官方动态_", ""), u))
            break
    return d, urls


def safe(s):
    return re.sub(r"[\\/:*?\"<>|]", "_", s)[:60]


def dismiss(pg):
    """尝试关掉 cookie/订阅浮层：按 Esc、遍历 iframe、移除固定浮层、点关闭。"""
    try:
        pg.keyboard.press("Escape")
    except Exception:
        pass
    js = """() => {
      const pats = [/cookie/i,/consent/i,/gdpr/i,/newsletter/i,/subscribe/i,/paywall/i,/member/i,/modal/i,/popup/i];
      document.querySelectorAll('div,section,aside,dialog,form,iframe').forEach(el => {
        const tag = (el.id||'') + ' ' + (el.className||'');
        const st = getComputedStyle(el);
        const r = el.getBoundingClientRect();
        if ((st.position === 'fixed' || st.position === 'sticky') &&
            r.width > 180 && r.height > 100) {
          const txt = (el.innerText || '').slice(0, 300);
          if (pats.some(p => p.test(tag)) ||
              /(sign up|subscribe|newsletter|member|cookie|consent|privacy|accept)/i.test(txt)) {
            el.remove();
          }
        }
      });
      document.querySelectorAll('button,[role=button],a,span,div').forEach(b => {
        const a = (b.getAttribute('aria-label')||'') + ' ' + (b.innerText||'');
        if (/^(close|dismiss|×|✕|✖)$/i.test(a.trim())) {
          const r = b.getBoundingClientRect();
          if (r.width > 0 && r.width < 120 && r.height < 120) { try { b.click(); } catch(e) {} }
        }
      });
    }"""
    for fr in list(pg.frames):
        try:
            fr.evaluate(js)
        except Exception:
            continue
    pg.wait_for_timeout(500)


def shot_page(pg, outdir, tag, url):
    shots = outdir / "截图"
    videos = outdir / "录屏"
    shots.mkdir(parents=True, exist_ok=True)
    videos.mkdir(parents=True, exist_ok=True)
    try:
        pg.goto(url, timeout=45000, wait_until="domcontentloaded")
    except Exception as e:
        return {"tag": tag, "url": url, "ok": False, "err": str(e)[:120]}
    pg.wait_for_timeout(2500)
    dismiss(pg)
    try:
        pg.wait_for_function("document.fonts && document.fonts.status === 'loaded'", timeout=8000)
    except Exception:
        pass
    # 滚动触发懒加载
    try:
        for y in range(0, 6000, 600):
            pg.evaluate(f"window.scrollTo(0,{y})")
            pg.wait_for_timeout(120)
        pg.evaluate("window.scrollTo(0,0)")
        pg.wait_for_timeout(400)
    except Exception:
        pass

    info = {"tag": tag, "url": url, "ok": True, "files": []}
    # 1) 整页长图
    try:
        p = shots / f"{tag}_整页.png"
        pg.screenshot(path=str(p), full_page=True, timeout=60000, animations="disabled")
        info["files"].append(str(p.relative_to(outdir)))
    except Exception as e:
        info["err_full"] = str(e)[:100]
    # 2) 标题区
    try:
        h = pg.query_selector("h1") or pg.query_selector("title")
        if h:
            p = shots / f"{tag}_标题.png"
            h.screenshot(path=str(p))
            info["files"].append(str(p.relative_to(outdir)))
    except Exception:
        pass
    # 3) 滚动分镜（4 张）
    try:
        h = pg.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)") or 1000
        for i, frac in enumerate((0.0, 0.33, 0.66, 0.9)):
            y = max(0, int((h - VH) * frac))
            try:
                pg.evaluate(f"window.scrollTo(0, {y})")
                pg.wait_for_timeout(300)
                p = shots / f"{tag}_滚动{i+1}.png"
                pg.screenshot(path=str(p), timeout=20000, animations="disabled")
                info["files"].append(str(p.relative_to(outdir)))
            except Exception:
                continue
    except Exception:
        pass
    # 4) 页面大图（人物/图表）
    try:
        imgs = pg.eval_on_selector_all("img", "els => els.map(e => ({src:e.src, w:e.naturalWidth, h:e.naturalHeight, alt:e.alt||''})).filter(x => x.w>=400 && x.h>=250).slice(0,5)")
        for i, im in enumerate(imgs):
            try:
                req = urllib.request.Request(im["src"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                ext = ".png" if im["src"].lower().endswith(".png") else ".jpg"
                p = shots / f"{tag}_图片{i+1}{ext}"
                p.write_bytes(data)
                info["files"].append(str(p.relative_to(outdir)))
            except Exception:
                continue
    except Exception:
        pass
    # 5) 滚动录屏：用分镜拼视频（12 帧）
    try:
        fr_dir = outdir / "录屏" / f"_frames_{tag}"
        fr_dir.mkdir(parents=True, exist_ok=True)
        h = pg.evaluate("Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)") or 1000
        steps = 36
        for i in range(steps):
            y = int((h - VH) * i / (steps - 1)) if h > VH else 0
            pg.evaluate(f"window.scrollTo(0,{max(0,y)})")
            pg.wait_for_timeout(120)
            if i % 6 == 0:
                dismiss(pg)
            pg.screenshot(path=str(fr_dir / f"f_{i:03d}.png"), timeout=20000, animations="disabled")
        mp4 = videos / f"{tag}_滚动.mp4"
        cmd = [str(FFMPEG), "-y", "-framerate", "8", "-i", str(fr_dir / "f_%03d.png"),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
               "-vf", "scale=1080:-2", str(mp4)]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            info["files"].append(str(mp4.relative_to(outdir)))
        import shutil
        shutil.rmtree(fr_dir, ignore_errors=True)
    except Exception as e:
        info["err_video"] = str(e)[:100]
    return info


def capture_people():
    d = BASE / "关键人物"
    d.mkdir(parents=True, exist_ok=True)
    out = []
    for label, page in PEOPLE:
        try:
            api = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page)}"
            req = urllib.request.Request(api, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode())
            src = (data.get("thumbnail") or {}).get("source", "")
            if not src:
                out.append({"label": label, "ok": False})
                continue
            req = urllib.request.Request(src, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                data_b = r.read()
            ext = ".png" if src.lower().endswith(".png") else ".jpg"
            p = d / f"{safe(label)}{ext}"
            p.write_bytes(data_b)
            (d / f"{safe(label)}_来源.txt").write_text(
                f"人物：{label}\nWikipedia: https://en.wikipedia.org/wiki/{page}\n图片: {src}\n授权：以 Wikimedia Commons 页面标注为准（多为 CC BY-SA）\n",
                encoding="utf-8")
            out.append({"label": label, "ok": True, "file": str(p.relative_to(BASE))})
            print(f"  people: {label} ok")
        except Exception as e:
            out.append({"label": label, "ok": False, "err": str(e)[:80]})
            print(f"  people: {label} fail {e}")
    (d / "_people.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--people", action="store_true")
    a = ap.parse_args()
    if a.people:
        capture_people()
        return

    from patchright.sync_api import sync_playwright
    slugs = [a.only] if a.only else [p.name for p in sorted(BASE.iterdir()) if p.is_dir() and p.name[0].isdigit()]
    man = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(CHROME), headless=True,
                               args=["--no-sandbox", "--disable-gpu", "--hide-scrollbars"])
        for slug in slugs:
            d, urls = pick_urls(slug)
            print(f"\n[{slug}] {len(urls)} pages")
            for tag, url in urls:
                pg = b.new_page(viewport={"width": VW, "height": VH}, device_scale_factor=1)
                try:
                    info = shot_page(pg, d, safe(tag), url)
                finally:
                    pg.close()
                man.append(info)
                print(f"  {tag}: {'ok' if info.get('ok') else 'FAIL'} files={len(info.get('files', []))}")
                time.sleep(0.5)
        b.close()
    (BASE / "_visual_manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n完成 pages:", len(man), " 截图/录屏文件:", sum(len(m.get("files", [])) for m in man))


if __name__ == "__main__":
    main()
