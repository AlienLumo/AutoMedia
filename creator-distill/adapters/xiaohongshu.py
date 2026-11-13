# -*- coding: utf-8 -*-
"""xiaohongshu adapter — 单博主取数（元数据 + 视频 + 抽帧 + ASR）。

只读；输出符合 schema v1 的 creator.json。
独立实现（不 import 采集器代码），只复用项目 runtime 与登录 profile。
"""
import json
import os
import re
import subprocess
import sys
import time
import random
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

_SKILL = Path(__file__).resolve().parent.parent
if str(_SKILL) not in sys.path:
    sys.path.insert(0, str(_SKILL))
from scripts._paths import PROJECT as PROJ, PROFILE, CHROME, FFMPEG, RUNTIME  # noqa: E402

os.environ.setdefault("HF_HOME", str(RUNTIME / "models" / "huggingface"))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

CARD_JS = r"""
() => Array.from(document.querySelectorAll("section.note-item, div.note-item"))
  .map(sec => {
    const txt = el => el ? (el.innerText || '').trim() : '';
    const anchors = Array.from(sec.querySelectorAll("a[href]"));
    const noteA = anchors.find(a => /\/search_result\/[0-9a-f]+/.test(a.getAttribute('href') || ''))
               || anchors.find(a => /\/explore\/[0-9a-f]+/.test(a.getAttribute('href') || ''));
    if (!noteA) return null;
    const href = noteA.getAttribute('href') || '';
    const idm = href.match(/\/(?:search_result|explore)\/([0-9a-f]+)/);
    const token = (href.match(/xsec_token=([^&]+)/) || [])[1] || '';
    const footer = txt(sec.querySelector('.footer'));
    return {href, token, note_id: idm ? idm[1] : '',
            title: txt(sec.querySelector('.footer .title, .note-title')) || footer.split('\n')[0] || '',
            author: txt(sec.querySelector('.author .name, .author-wrapper .name, .card-bottom-wrapper .name')),
            like: txt(sec.querySelector('.like-wrapper .count, .like-wrapper')),
            date: (footer.match(/\d{2}-\d{2}|\d{4}-\d{2}-\d{2}|昨天|今天/) || [''])[0]};
  }).filter(x => x && x.note_id)
"""

DETAIL_JS = r"""
() => {
  const t = s => { const el = document.querySelector(s); return el ? (el.innerText || '').trim() : ''; };
  const authorLink = document.querySelector(".author-wrapper a[href*='/user/profile/'], .note-content .author a[href*='/user/profile/']")
                     || document.querySelector("a[href*='/user/profile/']");
  let desc = '';
  for (const s of ["#detail-desc .note-text", "#detail-desc", ".note-text", ".note-content .desc", ".desc"]) {
    const v = t(s); if (v.length > desc.length) desc = v;
  }
  return {
    title: t("#detail-title") || t("h1"), desc,
    tags: Array.from(document.querySelectorAll("#detail-desc a, .note-content a"))
      .map(a => (a.innerText || '').trim()).filter(x => x.startsWith('#')),
    counts: Array.from(document.querySelectorAll(".engage-bar .count, .interact-container .count"))
      .map(e => (e.innerText || '').trim()),
    has_video: !!document.querySelector("video"),
    author: t(".author-wrapper .username, .author-wrapper .name, .username"),
    author_id: authorLink ? ((authorLink.getAttribute('href') || '').match(/profile\/([0-9a-f]+)/) || [])[1] || '' : '',
    date_text: t(".bottom-container .date, .note-content .date, .date"),
    url: location.href
  };
}
"""


def parse_num(t):
    if not t:
        return None
    t = str(t).strip()
    m = re.search(r"([\d.]+)\s*万", t)
    if m:
        return int(float(m.group(1)) * 10000)
    m = re.search(r"(\d+)", t.replace(",", ""))
    return int(m.group(1)) if m else None


def run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "ignore")[:300])
    return r.stdout


def download(url, path, referer="https://www.xiaohongshu.com/"):
    req = urllib.request.Request(url.replace("&amp;", "&"),
                                 headers={"User-Agent": UA, "Referer": referer})
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=120) as r, path.open("wb") as f:
        f.write(r.read())
    return path


def probe_duration(video):
    try:
        r = subprocess.run([str(FFMPEG), "-i", str(video)], capture_output=True, timeout=60)
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", r.stderr.decode("utf-8", "ignore"))
        if m:
            h, mi, s = m.groups()
            return int(h) * 3600 + int(mi) * 60 + float(s)
    except Exception:
        pass
    return 0


def grab_video_url(page):
    html = page.content()
    urls = re.findall(r'https?://[^"\']+\.mp4[^"\']*', html)
    if not urls:
        return ""
    return urls[0].replace("&amp;", "&")


def extract_frames(video, frames_dir, count=4):
    frames_dir.mkdir(parents=True, exist_ok=True)
    dur = probe_duration(video)
    out = []
    for i in range(count):
        ts = max(0.0, dur * (i + 1) / (count + 1))
        p = frames_dir / f"frame_{i+1:02d}.jpg"
        try:
            run([str(FFMPEG), "-y", "-ss", f"{ts:.2f}", "-i", str(video),
                 "-frames:v", "1", "-q:v", "3", str(p)], timeout=120)
            if p.exists() and p.stat().st_size > 0:
                out.append(str(p))
        except Exception:
            pass
    # 联系表（tile）
    if out:
        sheet = frames_dir / "contact_sheet.jpg"
        try:
            pat = str(frames_dir / "frame_%02d.jpg")
            run([str(FFMPEG), "-y", "-i", str(frames_dir / "frame_%02d.jpg"),
                 "-filter_complex", "tile=2x2:padding=6:margin=6", "-frames:v", "1", str(sheet)],
                timeout=120)
            if sheet.exists():
                out.append(str(sheet))
        except Exception:
            pass
    return out


def transcribe(video, work_dir):
    from faster_whisper import WhisperModel
    wav = work_dir / "audio.wav"
    run([str(FFMPEG), "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        timeout=600)
    # 直接用 wave 读 16k wav，绕开 PyAV 版本不兼容（metadata_errors 参数）
    import wave
    import numpy as np
    with wave.open(str(wav), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    model = WhisperModel("large-v3", device="cuda", compute_type="int8_float16")
    segments, info = model.transcribe(
        audio, language="zh", vad_filter=True, beam_size=5,
        initial_prompt="以下是普通话情景短剧，主题是心理学与社会学现象，请使用规范的中文标点符号。",
        condition_on_previous_text=False)
    segs, texts = [], []
    for s in segments:
        segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
        texts.append(s.text.strip())
    return {"source": "asr", "lang": "zh", "text": "".join(texts), "segments": segs}


def norm_date(t):
    t = (t or "").strip()
    m = re.match(r"(\d{2})-(\d{2})", t)
    if m:
        return f"2026-{m.group(1)}-{m.group(2)}"
    return t


ANCHOR_TAGS = ("心理学", "社会学", "经济学", "涨知识", "有趣的事实", "管理学", "认知")


def clean_title(t):
    t = (t or "").replace("\ufeff", "").strip()
    t = re.split(r"[#＃]", t)[0].strip()
    changed = True
    while changed:
        changed = False
        t = t.strip()
        for w in ANCHOR_TAGS:
            if t.endswith(w):
                t = t[: -len(w)].strip()
                changed = True
    return t.strip()


REUPLOAD_HINTS = ("请不吝点赞", "订阅", "打赏", "明镜与点点", "栏目")


def is_reupload(text):
    hits = [h for h in REUPLOAD_HINTS if h in (text or "")]
    return len(hits) >= 2


def fetch(creator_name, out_dir, max_works=30, detail_works=3, with_asr=True,
          with_frames=True, frames=4, headless=True):
    from patchright.sync_api import sync_playwright
    out_dir.mkdir(parents=True, exist_ok=True)
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        str(PROFILE), executable_path=str(CHROME), headless=headless,
        args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--no-first-run"],
        locale="zh-CN", viewport={"width": 1400, "height": 900}, user_agent=UA)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    media_urls = []

    def _on_resp(r):
        try:
            u = r.url or ""
            if ".mp4" in u and "xhscdn" in u:
                media_urls.append(u)
        except Exception:
            pass

    page.on("response", _on_resp)

    def goto(url, wait=4500):
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(wait)

    def cards(scrolls=1):
        out = []
        for i in range(scrolls + 1):
            out += page.evaluate(CARD_JS) or []
            if i < scrolls:
                page.mouse.wheel(0, 900)
                page.wait_for_timeout(1800)
        seen, rows = set(), []
        for c in out:
            if c["note_id"] in seen:
                continue
            seen.add(c["note_id"])
            rows.append(c)
        return rows

    def open_note(note_id, token):
        media_urls.clear()
        url = f"https://www.xiaohongshu.com/search_result/{note_id}?xsec_source=pc_search"
        if token:
            url += f"&xsec_token={token}"
        goto(url, wait=6000)
        d = page.evaluate(DETAIL_JS)
        d["note_id"] = note_id
        try:
            d["page_video_duration"] = page.evaluate(
                "() => { const v = document.querySelector('video');"
                " return v && isFinite(v.duration) ? v.duration : 0; }")
        except Exception:
            d["page_video_duration"] = 0
        cands = list(dict.fromkeys(media_urls))
        d["candidates"] = cands
        # 兜底：页面里搜 mp4（可能是推荐位，用时长校验剔除）
        if not cands and d.get("has_video"):
            fallback = grab_video_url(page)
            if fallback:
                cands = [fallback]
                d["candidates"] = cands
        d["video_url"] = cands[0] if cands else ""
        return d

    try:
        goto("https://www.xiaohongshu.com/search_result?keyword="
             + urllib.parse.quote(creator_name) + "&source=web_search_result_notes", wait=4500)
        hits = cards(1)
        mine = [h for h in hits if creator_name in (h.get("author") or "")]
        if not mine:
            mine = hits[:3]
        first = open_note(mine[0]["note_id"], mine[0].get("token") or "")
        uid = first.get("author_id") or ""
        # 主页列表
        goto(f"https://www.xiaohongshu.com/user/profile/{uid}", wait=5000)
        rows, seen = [], set()
        for _ in range(4):
            for c in cards(0):
                if c["note_id"] in seen:
                    continue
                seen.add(c["note_id"])
                rows.append(c)
            if len(rows) >= max_works:
                break
            page.mouse.wheel(0, 1200)
            page.wait_for_timeout(1800)

        creator = {"id": uid, "name": creator_name,
                   "url": f"https://www.xiaohongshu.com/user/profile/{uid}"}
        works = []
        for i, c in enumerate(rows[:max_works]):
            w = {
                "work_id": c["note_id"], "url": "https://www.xiaohongshu.com/explore/" + c["note_id"],
                "title": clean_title(c.get("title") or ""), "desc": "", "published_at": norm_date(c.get("date")),
                "format": "unknown",
                "metrics": {"like": parse_num(c.get("like")), "view": None, "comment": None,
                            "collect": None, "share": None},
                "tags": [], "cover_url": "", "media_url": "", "frames": []
            }
            works.append(w)

        # 详情 + 视频 + 抽帧 + ASR（只对前 detail_works 条）
        by_like = sorted(works, key=lambda x: -(x["metrics"]["like"] or 0))
        target_ids = {w["work_id"] for w in by_like[:detail_works]}
        for w in works:
            if w["work_id"] not in target_ids:
                continue
            cand = next((c for c in rows if c["note_id"] == w["work_id"]), {})
            tok = cand.get("token") or ""
            if not tok:
                try:
                    goto("https://www.xiaohongshu.com/search_result?keyword="
                         + urllib.parse.quote(w["title"][:20]) + "&source=web_search_result_notes", wait=3500)
                    hh = [x for x in cards(0) if x["note_id"] == w["work_id"]]
                    tok = hh[0].get("token") if hh else ""
                except Exception:
                    tok = ""
            try:
                d = open_note(w["work_id"], tok)
            except Exception as e:
                print(f"  ! detail {w['work_id']}: {e}", file=sys.stderr)
                continue
            w["desc"] = d.get("desc") or ""
            w["tags"] = d.get("tags") or []
            w["format"] = "video" if d.get("has_video") else "image_text"
            w["published_at"] = d.get("date_text") or w["published_at"]
            if d.get("title"):
                w["title"] = d["title"].strip()
            counts = d.get("counts") or []
            if len(counts) >= 3:
                w["metrics"].update({"like": parse_num(counts[0]) or w["metrics"]["like"],
                                     "collect": parse_num(counts[1]),
                                     "comment": parse_num(counts[2])})
            wdir = out_dir / "works" / w["work_id"]
            wdir.mkdir(parents=True, exist_ok=True)
            (wdir / "detail.json").write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
            cands = d.get("candidates") or ([d["video_url"]] if d.get("video_url") else [])
            page_dur = d.get("page_video_duration") or 0
            if d.get("has_video") and cands:
                media = None
                used_url = ""
                for idx, u in enumerate(cands[:4]):
                    tmp = wdir / f"_cand{idx}.mp4"
                    try:
                        download(u, tmp)
                        dur = probe_duration(tmp)
                        print(f"  · cand{idx} dur={dur:.1f}s page={page_dur:.1f}s", file=sys.stderr)
                        if media is None:
                            media, used_url = tmp, u
                        if not page_dur or abs(dur - page_dur) <= 5:
                            media, used_url = tmp, u
                            break
                    except Exception as e:
                        print(f"  ! cand{idx}: {str(e)[:60]}", file=sys.stderr)
                if media is not None:
                    target = wdir / "video.mp4"
                    try:
                        if target.exists():
                            target.unlink()
                        media.replace(target)
                    except Exception:
                        target = media
                    w["media_url"] = used_url
                    d["video_url"] = used_url
                    (wdir / "detail.json").write_text(
                        json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
                    w["local_media"] = str(target)
                    w["duration_sec"] = round(probe_duration(target), 1)
                    if with_frames:
                        imgs = extract_frames(target, wdir / "frames", count=frames)
                        w["frames"] = imgs
                        w["contact_sheet"] = str(wdir / "frames" / "contact_sheet.jpg") \
                            if (wdir / "frames" / "contact_sheet.jpg").exists() else ""
                    if with_asr:
                        try:
                            tr = transcribe(target, wdir)
                            w["transcript"] = tr
                            w["likely_reupload"] = is_reupload(tr.get("text"))
                            (wdir / "transcript.json").write_text(
                                json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
                        except Exception as e:
                            print(f"  ! asr {w['work_id']}: {e}", file=sys.stderr)
            elif d.get("has_video") is False:
                w["transcript"] = {"source": "desc", "lang": "zh", "text": w["desc"], "segments": []}
        data = {"schema_version": 1, "platform": "xiaohongshu",
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "creator": creator, "works": works}
        (out_dir / "creator.json").write_text(json.dumps(data, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
        return data
    finally:
        try:
            ctx.close()
        finally:
            pw.stop()




