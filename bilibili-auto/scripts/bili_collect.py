#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_collect.py — 单个 UP 主最近 N 个视频的「元数据 + 评论 + 逐字稿」采集。

为此前 bili_subs.py 的升级版：一次跑完三样数据，按视频分目录，全部断点续传。

用法
  # 免登录：只拿元数据 + 热评预览（会明确提示评论被限制）
  python bili_collect.py --mid 385670211 --limit 50 --outdir data/秋芝2046

  # 登录后：全量评论 + CC/AI 字幕
  python bili_collect.py --mid 385670211 --limit 50 --outdir data/秋芝2046 \
      --with-comments --with-subs

输出
  <outdir>/manifest.json            总表（每个视频的采集状态与统计）
  <outdir>/videos.jsonl             视频元数据
  <outdir>/<bvid>_<title>/meta.json
  <outdir>/<bvid>_<title>/comments.jsonl
  <outdir>/<bvid>_<title>/transcript.zh.srt / .txt
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import (Bili, Throttled, Budget, NotLoggedIn, read_cred, mask,
                       safe_name, to_srt, DM_PARAMS, cred_summary)   # noqa: E402


def load_done(path):
    done = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                done.add(json.loads(line)["bvid"])
            except Exception:
                pass
    return done


def append_jsonl(path, obj):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def collect_meta(b, v):
    r = b.get("x/web-interface/view", {"bvid": v["bvid"]})
    d = r["data"]
    st = d.get("stat") or {}
    try:
        tags = [t.get("tag_name") for t in
                (b.get("x/tag/archive/tags", {"bvid": d["bvid"]}).get("data") or [])]
    except Exception:
        tags = []
    return {
        "bvid": d["bvid"], "aid": d["aid"], "cid": d["cid"],
        "title": d["title"], "desc": d.get("desc") or "",
        "duration": d.get("duration"), "pubdate": d.get("pubdate"),
        "pubdate_str": time.strftime("%Y-%m-%d %H:%M",
                                     time.localtime(d.get("pubdate") or 0)),
        "owner": (d.get("owner") or {}).get("name"),
        "pages": len(d.get("pages") or []),
        "view": st.get("view"), "like": st.get("like"), "coin": st.get("coin"),
        "favorite": st.get("favorite"), "share": st.get("share"),
        "danmaku": st.get("danmaku"), "reply": st.get("reply"),
        "tags": tags,
    }


def collect_comments(b, aid, cap=500, nested_pages=2):
    """Top-level comments (hot order) + nested replies. Returns list."""
    out, cursor, got = [], 0, 0
    while got < cap:
        r = b.get("x/v2/reply/wbi/main",
                  {"type": 1, "oid": aid, "mode": 3, "next": cursor,
                   "ps": 20, "plat": 1})
        dd = r.get("data") or {}
        reps = dd.get("replies") or []
        if not reps:
            break
        for c in reps:
            out.append({
                "rpid": c.get("rpid"), "parent": c.get("parent"),
                "member": (c.get("member") or {}).get("uname"),
                "mid": (c.get("mid") or 0), "like": c.get("like"),
                "ctime": c.get("ctime"),
                "ctime_str": time.strftime("%Y-%m-%d",
                                           time.localtime(c.get("ctime") or 0)),
                "message": (c.get("content") or {}).get("message", ""),
                "rcount": c.get("rcount"),
            })
            got += 1
            # nested replies (楼中楼) — 匿名也能拿一部分
            if nested_pages and (c.get("rcount") or 0) > 0:
                for pn in range(1, nested_pages + 1):
                    try:
                        rr = b.get("x/v2/reply/reply",
                                   {"type": 1, "oid": aid, "root": c["rpid"],
                                    "pn": pn, "ps": 20})
                    except (Throttled, Budget):
                        raise
                    except Exception:
                        break
                    sub = ((rr.get("data") or {}).get("replies")) or []
                    if not sub:
                        break
                    for s in sub:
                        out.append({
                            "rpid": s.get("rpid"), "parent": s.get("parent"),
                            "root": c["rpid"],
                            "member": (s.get("member") or {}).get("uname"),
                            "mid": (s.get("mid") or 0), "like": s.get("like"),
                            "ctime": s.get("ctime"),
                            "ctime_str": time.strftime(
                                "%Y-%m-%d", time.localtime(s.get("ctime") or 0)),
                            "message": (s.get("content") or {}).get("message", ""),
                        })
                        got += 1
                    time.sleep(b.pace)
                    if pn * 20 >= (c.get("rcount") or 0):
                        break
        cur = dd.get("cursor") or {}
        if cur.get("is_end"):
            break
        cursor = cur.get("next") or (cursor + 1)
        time.sleep(b.pace)
    return out


def collect_subs(b, aid, cid, updir, base, sub_langs=None):
    r = b.get("x/player/wbi/v2", {"aid": aid, "cid": cid})
    subs = (((r.get("data") or {}).get("subtitle")) or {}).get("subtitles") or []
    files = []
    for s in subs:
        lan = (s.get("lan") or "zh")
        if sub_langs:
            toks = [x for x in lan.lower().replace("_", "-").split("-") if x]
            if not any(f in toks for f in sub_langs):
                continue
        url = s.get("subtitle_url") or ""
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            continue
        try:
            data = b._raw(url)
        except Exception as e:
            print(f"    ! subtitle dl failed: {e}", file=sys.stderr)
            continue
        body = data.get("body") or []
        if not body:
            continue
        lan = (s.get("lan") or "zh").replace("/", "_")
        (updir / f"{base}.{lan}.srt").write_text(to_srt(body), encoding="utf-8")
        (updir / f"{base}.{lan}.txt").write_text(
            "\n".join((x.get("content") or "").strip() for x in body),
            encoding="utf-8")
        files.append(f"{base}.{lan}")
        time.sleep(b.pace)
    return files, len(subs)


def list_videos(b, mid, uname, limit, order="pubdate", source="auto"):
    """视频列表双通道：space 投稿接口优先，失败自动回退到搜索接口。

    space 接口（arc/search）最容易被 -352 拦，且必须带 dm_img 参数；
    搜索接口（search/type+order=pubdate）稳定得多，按发布时间倒序，
    正好满足「最近 N 个视频」的需求。
    """
    if source in ("auto", "space"):
        try:
            vids = b.videos(mid, limit, order)
            if vids:
                print(f"[list] space 接口: {len(vids)} videos", file=sys.stderr)
                return vids
        except (Throttled, Budget) as e:
            if source == "space":
                raise
            print(f"[fallback] space 接口失败({type(e).__name__})，改用搜索接口",
                  file=sys.stderr)

    got = {}
    for pn in range(1, 13):
        try:
            r = b.get("x/web-interface/wbi/search/type",
                      {"search_type": "video", "keyword": uname, "page": pn,
                       "order": "pubdate"}, tries=2)
        except (Throttled, Budget) as e:
            print(f"[fallback] 搜索第{pn}页失败: {e}", file=sys.stderr)
            break
        res = (r.get("data") or {}).get("result") or []
        if not res:
            break
        for v in res:
            if v.get("mid") != mid:
                continue
            title = (v.get("title") or "")
            for tag in ('<em class="keyword">', "</em>"):
                title = title.replace(tag, "")
            got.setdefault(v["bvid"], {
                "bvid": v["bvid"], "aid": v.get("aid"), "title": title,
                "play": v.get("play"), "created": v.get("pubdate"),
                "length": v.get("duration"),
            })
        if len(got) >= limit:
            break
        time.sleep(b.pace)
    vids = list(got.values())[:limit]
    print(f"[list] 搜索接口: {len(vids)} videos", file=sys.stderr)
    return vids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mid", type=int, required=True)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--order", default="pubdate", help="pubdate|click")
    ap.add_argument("--list-source", default="auto", dest="list_source",
                    choices=["auto", "space", "search"],
                    help="视频列表来源：space 接口更全但易被拦，search 更稳")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--with-comments", action="store_true", dest="with_comments")
    ap.add_argument("--comment-cap", type=int, default=500, dest="comment_cap")
    ap.add_argument("--with-subs", action="store_true", dest="with_subs")
    ap.add_argument("--pace", type=float, default=1.2)
    ap.add_argument("--cooldown", type=int, default=60)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--cred-file", default=None, dest="cred_file")
    ap.add_argument("--allow-anon", action="store_true", dest="allow_anon")
    a = ap.parse_args()

    outdir = Path(a.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path = outdir / "manifest.json"
    videos_jsonl = outdir / "videos.jsonl"
    done = load_done(videos_jsonl)

    cred = read_cred(a.cred_file)
    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=cred)
    print(f"[cred] {cred_summary(cred)} ",
          file=sys.stderr)
    try:
        b.preflight()
    except NotLoggedIn as e:
        print(f"[NO-LOGIN] {e}", file=sys.stderr)
        if not a.allow_anon:
            print("[hint] 想要全量评论和字幕必须登录；只想试元数据可加 --allow-anon",
                  file=sys.stderr)
            raise SystemExit(3)
        print("[warn] 匿名模式：评论只会有 3 条热评预览，字幕为空", file=sys.stderr)

    # 1) 视频列表（双通道自动回退）
    try:
        card = b.get("x/web-interface/card", {"mid": a.mid}).get("data") or {}
        uname = (card.get("card") or {}).get("name") or str(a.mid)
    except (Throttled, Budget):
        uname = str(a.mid)
    print(f"[up] {uname} ({a.mid})", file=sys.stderr)
    vids = list_videos(b, a.mid, uname, a.limit, a.order, a.list_source)
    print(f"[list] {len(vids)} videos ready", file=sys.stderr)

    stats = {"videos": 0, "meta": 0, "comments": 0, "subs_videos": 0,
             "sub_files": 0, "skipped": 0, "errors": 0}
    try:
        for v in vids:
            if v["bvid"] in done:
                stats["skipped"] += 1
                continue
            stats["videos"] += 1
            updir = outdir / f'{v["bvid"]}_{safe_name(v["title"], 40)}'
            updir.mkdir(parents=True, exist_ok=True)
            base = f'{v["bvid"]}_{safe_name(v["title"], 40)}'
            rec = {"bvid": v["bvid"], "title": v["title"], "play": v["play"],
                   "created": v["created"], "comments": 0, "subs": 0,
                   "sub_files": [], "meta": False}
            try:
                meta = collect_meta(b, v)
                (updir / "meta.json").write_text(
                    json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                rec["meta"] = True
                stats["meta"] += 1
                aid, cid = meta["aid"], meta["cid"]
            except (Throttled, Budget):
                raise
            except Exception as e:
                print(f"  ! meta {v['bvid']}: {e}", file=sys.stderr)
                stats["errors"] += 1
                aid = cid = None

            if a.with_comments and aid:
                try:
                    cms = collect_comments(b, aid, a.comment_cap)
                    with (updir / "comments.jsonl").open("w", encoding="utf-8") as f:
                        for c in cms:
                            f.write(json.dumps(c, ensure_ascii=False) + "\n")
                    rec["comments"] = len(cms)
                    stats["comments"] += len(cms)
                except (Throttled, Budget):
                    raise
                except Exception as e:
                    print(f"  ! comments {v['bvid']}: {e}", file=sys.stderr)
                    stats["errors"] += 1

            if a.with_subs and aid and cid:
                try:
                    files, n = collect_subs(b, aid, cid, updir, base)
                    rec["subs"], rec["sub_files"] = n, files
                    if files:
                        stats["subs_videos"] += 1
                        stats["sub_files"] += len(files)
                except (Throttled, Budget):
                    raise
                except Exception as e:
                    print(f"  ! subs {v['bvid']}: {e}", file=sys.stderr)
                    stats["errors"] += 1

            append_jsonl(videos_jsonl, {**rec, "ts": time.time()})
            done.add(v["bvid"])
            print(f'  [{stats["videos"]:>2}/{len(vids)}] {v["title"][:32]} '
                  f'cm={rec["comments"]} subs={rec["subs"]}', file=sys.stderr)
            time.sleep(b.pace)
    except (Throttled, Budget) as e:
        print(f"\n[STOPPED] {e}", file=sys.stderr)
    except NotLoggedIn as e:
        print(f"\n[NO-LOGIN] {e}", file=sys.stderr)

    # manifest
    rows = []
    if videos_jsonl.exists():
        for line in videos_jsonl.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    manifest_path.write_text(json.dumps(
        {"mid": a.mid, "count": len(rows), "stats": stats, "videos": rows},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[stats] {stats}", file=sys.stderr)
    print(f"[out] {outdir}  ({len(rows)} videos recorded)", file=sys.stderr)


if __name__ == "__main__":
    main()
