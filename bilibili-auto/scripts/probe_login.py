# -*- coding: utf-8 -*-
"""Decisive test: use the project's existing biliup credential to (a) verify
login, (b) check whether subtitles are actually retrievable, (c) count
comment pagination depth. Never prints secret values."""
import json
import sys
from pathlib import Path
from _paths import PROJECT, SKILL, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
from bili_subs import Bili, to_srt

CRED = PROJECT / "data" / "sau" / "cookies" / "bilibili_alien.json"


def load_biliup_cred(path=CRED):
    d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    cookies = {}
    ci = d.get("cookie_info") or {}
    for item in (ci.get("cookies") or []):
        if isinstance(item, dict) and item.get("name"):
            cookies[item["name"]] = item.get("value", "")
    return cookies, d


cred, raw = load_biliup_cred()
print(f"[cred] 来源=biliup  platform={raw.get('platform')} mid={raw.get('mid')} "
      f"keys={sorted(cred)}")
b = Bili(pace=1.5, cooldown=30, cookies=cred)

print("\n=== 1) 登录态是否有效 ===")
try:
    b.preflight()
    valid = True
except Exception as e:
    print("  失效:", e)
    valid = False

if not valid:
    raise SystemExit(1)

print("\n=== 2) 字幕可得性（这是之前完全卡住的地方）===")
# 秋芝2046 的两个视频 + 花叔v 一个
targets = ["BV1PcJd6UE81", "BV1Nyp96pEGD", "BV1UZFfeMEvd"]
for bvid in targets:
    try:
        v = b.get("x/web-interface/view", {"bvid": bvid})["data"]
        r = b.get("x/player/wbi/v2", {"aid": v["aid"], "cid": v["cid"]})
        st = ((r.get("data") or {}).get("subtitle") or {})
        subs = st.get("subtitles") or []
        print(f"\n  {bvid} {v['title'][:30]}")
        print(f"     subtitles={len(subs)} allow_submit={st.get('allow_submit')}")
        for s in subs[:4]:
            print(f"       lan={s.get('lan')} doc={s.get('lan_doc')} "
                  f"ai_type={s.get('ai_type')} url_present={bool(s.get('subtitle_url'))}")
        if subs:
            url = subs[0].get("subtitle_url") or ""
            if url.startswith("//"):
                url = "https:" + url
            data = b._raw(url)
            body = data.get("body") or []
            print(f"     下载成功: {len(body)} 条字幕")
            for line in body[:3]:
                print(f"       [{line.get('from')}s] {(line.get('content') or '')[:40]}")
            out = SKILL / "data" / "_probe"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{bvid}.zh.srt").write_text(to_srt(body), encoding="utf-8")
    except Exception as e:
        print(f"  {bvid} ERR {e}")

print("\n=== 3) 评论全量是否解锁 ===")
v = b.get("x/web-interface/view", {"bvid": "BV1UZFfeMEvd"})["data"]
r = b.get("x/v2/reply/wbi/main",
          {"type": 1, "oid": v["aid"], "mode": 3, "next": 0, "ps": 20, "plat": 1})
dd = r.get("data") or {}
print(f"  总评论数={(dd.get('cursor') or {}).get('all_count')} "
      f"本页={len(dd.get('replies') or [])} "
      f"is_end={(dd.get('cursor') or {}).get('is_end')}")
