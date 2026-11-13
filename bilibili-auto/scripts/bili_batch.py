#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_batch.py — 批量采集多个 UP 主，按「平台/主题/UP主/视频」四级目录落盘。

目录结构：
  <outroot>/bilibili/<主题>/<UP名>_<mid>/<bvid>_<标题>/
      meta.json
      comments.jsonl
      subtitle.<lan>.srt / .txt
  <outroot>/bilibili/_manifest.json    总清单

断点续传：视频目录里已有 meta.json 且（需要评论时）有 comments.jsonl 则跳过。

用法：
  python bili_batch.py --roster config/ups.tsv --limit-ups 30 --videos-per-up 2 \
      --comment-cap 500 --outroot <项目根>\1AMdata \
      --with-comments --with-subs --budget 900
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import (Bili, Throttled, Budget, NotLoggedIn, read_cred,   # noqa: E402
                       safe_name, to_srt)
from bili_collect import (collect_meta, collect_comments, collect_subs,   # noqa: E402
                          list_videos)

TOPIC_MAP = {
    "使用": "AI使用",
    "Agent": "Agent",
    "Skill": "Skill",
    "发展": "AI发展",
    "创作": "AIGC创作",
    "机构": "机构课程",
}


def read_roster(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        c = line.split("\t")
        try:
            mid = int(c[0])
        except ValueError:
            continue
        rows.append({
            "mid": mid,
            "name": c[1] if len(c) > 1 else str(mid),
            "topic_raw": c[2] if len(c) > 2 else "使用",
        })
    return rows


PREFIX_MAP = Path(__file__).resolve().parent.parent / "config" / "prefix_map.tsv"
FANS_JSON = Path(__file__).resolve().parent.parent / "config" / "fans.json"


def load_prefix_map():
    m = {}
    if PREFIX_MAP.exists():
        for line in PREFIX_MAP.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            c = line.split("\t")
            if len(c) < 4:
                continue
            try:
                m[int(c[0])] = {"name": c[1], "prefix": c[2], "fans": int(c[3] or 0)}
            except ValueError:
                pass
    return m


def load_fans():
    if FANS_JSON.exists():
        try:
            return json.loads(FANS_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def fmt_fans(n):
    return f"{n/10000:.1f}万" if n and n >= 10000 else str(n or 0)


def up_folder_name(mid, up_name, topic_raw, pmap, fans_map):
    """<前缀>_<UP名>_<粉丝量>"""
    info = pmap.get(mid)
    if info:
        return f'{info["prefix"]}_{safe_name(info["name"], 30)}_{fmt_fans(info["fans"])}'
    fans = (fans_map.get(str(mid)) or {}).get("fans") or 0
    pref = TOPIC_MAP.get(topic_raw, "ai")
    pref = {"AI使用": "ai", "AI发展": "商业", "AIGC创作": "ai",
            "Agent": "教程", "Skill": "教程", "机构课程": "教程"}.get(pref, "ai")
    return f"{pref}_{safe_name(up_name, 30)}_{fmt_fans(fans)}"


def video_dir(outroot, platform, topic, up_name, mid, bvid, title,
              pmap=None, fans_map=None):
    up = up_folder_name(mid, up_name, topic, pmap or {}, fans_map or {})
    d = (Path(outroot) / platform / up / f"{bvid}_{safe_name(title, 40)}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def already_done(vdir, need_comments, need_subs):
    if not (vdir / "meta.json").exists():
        return False
    if need_comments and not (vdir / "comments.jsonl").exists():
        return False
    if need_subs and not list(vdir.glob("subtitle.*.srt")):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster", required=True)
    ap.add_argument("--limit-ups", type=int, default=30, dest="limit_ups")
    ap.add_argument("--skip-ups", type=int, default=0, dest="skip_ups")
    ap.add_argument("--spread", action="store_true", help="按主题轮转抽样")
    ap.add_argument("--videos-per-up", type=int, default=2, dest="videos_per_up")
    ap.add_argument("--order", default="pubdate")
    ap.add_argument("--comment-cap", type=int, default=500, dest="comment_cap")
    ap.add_argument("--outroot", required=True)
    ap.add_argument("--platform", default="bilibili")
    ap.add_argument("--with-comments", action="store_true", dest="with_comments")
    ap.add_argument("--with-subs", action="store_true", dest="with_subs")
    ap.add_argument("--nested-pages", type=int, default=2, dest="nested_pages")
    ap.add_argument("--pace", type=float, default=1.2)
    ap.add_argument("--cooldown", type=int, default=60)
    ap.add_argument("--budget", type=int, default=0)
    ap.add_argument("--cred-file", default=None, dest="cred_file")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="只列出将采集的 UP 与目录，不发请求")
    a = ap.parse_args()

    pmap = load_prefix_map()
    fans_map = load_fans()
    roster = read_roster(a.roster)
    if a.spread:
        # 按主题轮转抽样，保证测试覆盖各分类而不是只取名单前 30 个
        buckets = {}
        for r in roster:
            buckets.setdefault(r["topic_raw"], []).append(r)
        order = sorted(buckets, key=lambda k: -len(buckets[k]))
        picked, i = [], 0
        while len(picked) < a.limit_ups and any(buckets[k] for k in order):
            for k in order:
                if buckets[k] and len(picked) < a.limit_ups:
                    picked.append(buckets[k].pop(0))
            i += 1
    else:
        picked = roster[a.skip_ups:a.skip_ups + a.limit_ups]
    print(f"[plan] 名单 {len(roster)} 个，本次取 {len(picked)} 个 "
          f"(skip={a.skip_ups}), 每号 {a.videos_per_up} 个视频, "
          f"评论上限 {a.comment_cap}", file=sys.stderr)
    for r in picked:
        topic = TOPIC_MAP.get(r["topic_raw"], r["topic_raw"])
        print(f"   {r['mid']:<12} {topic:<8} {r['name']}", file=sys.stderr)
    if a.dry_run:
        print(f"[dry-run] 输出根目录: {a.outroot}", file=sys.stderr)
        return

    cred = read_cred(a.cred_file)
    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=cred)
    try:
        b.preflight()
    except NotLoggedIn as e:
        print(f"[NO-LOGIN] {e}", file=sys.stderr)
        raise SystemExit(3)

    stats = {"ups": 0, "videos": 0, "skipped": 0, "meta": 0, "comments": 0,
             "subs_videos": 0, "sub_files": 0, "errors": 0, "no_subs": 0}
    manifest = []
    t0 = time.time()
    try:
        for r in picked:
            print(f"\n=== [{stats['ups']+1}/{len(picked)}] {r['name']} ({r['mid']})",
                  file=sys.stderr)
            try:
                vids = list_videos(b, r["mid"], r["name"], a.videos_per_up,
                                   a.order, "auto")
            except (Throttled, Budget):
                raise
            except Exception as e:
                print(f"  ! 列表失败: {e}", file=sys.stderr)
                stats["errors"] += 1
                continue
            stats["ups"] += 1
            for v in vids:
                stats["videos"] += 1
                vdir = video_dir(a.outroot, a.platform, r["topic_raw"], r["name"],
                                 r["mid"], v["bvid"], v["title"])
                if already_done(vdir, a.with_comments, a.with_subs):
                    stats["skipped"] += 1
                    print(f"   skip {v['bvid']}", file=sys.stderr)
                    continue
                rec = {"platform": a.platform, "topic": r["topic_raw"],
                       "up": r["name"], "mid": r["mid"], "bvid": v["bvid"],
                       "title": v["title"], "dir": str(vdir),
                       "comments": 0, "subs": 0, "sub_files": []}
                try:
                    meta = collect_meta(b, v)
                    (vdir / "meta.json").write_text(
                        json.dumps(meta, ensure_ascii=False, indent=1),
                        encoding="utf-8")
                    stats["meta"] += 1
                    aid, cid = meta["aid"], meta["cid"]
                except (Throttled, Budget):
                    raise
                except Exception as e:
                    print(f"   ! meta {v['bvid']}: {e}", file=sys.stderr)
                    stats["errors"] += 1
                    continue

                if a.with_comments:
                    try:
                        cms = collect_comments(b, aid, a.comment_cap,
                                               a.nested_pages)
                        with (vdir / "comments.jsonl").open("w", encoding="utf-8") as f:
                            for c in cms:
                                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                        rec["comments"] = len(cms)
                        stats["comments"] += len(cms)
                    except (Throttled, Budget):
                        raise
                    except Exception as e:
                        print(f"   ! comments {v['bvid']}: {e}", file=sys.stderr)
                        stats["errors"] += 1

                if a.with_subs:
                    try:
                        files, n = collect_subs(b, aid, cid, vdir, "subtitle")
                        rec["subs"], rec["sub_files"] = n, files
                        if files:
                            stats["subs_videos"] += 1
                            stats["sub_files"] += len(files)
                        else:
                            stats["no_subs"] += 1
                    except (Throttled, Budget):
                        raise
                    except Exception as e:
                        print(f"   ! subs {v['bvid']}: {e}", file=sys.stderr)
                        stats["errors"] += 1

                manifest.append(rec)
                print(f"   ok {v['bvid']} cm={rec['comments']} subs={rec['subs']} "
                      f"({time.time()-t0:.0f}s)", file=sys.stderr)
    except (Throttled, Budget) as e:
        print(f"\n[STOPPED] {e}", file=sys.stderr)
    except NotLoggedIn as e:
        print(f"\n[NO-LOGIN] {e}", file=sys.stderr)

    mpath = Path(a.outroot) / a.platform / "_manifest.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    old = []
    if mpath.exists():
        try:
            old = json.loads(mpath.read_text(encoding="utf-8")).get("items", [])
        except Exception:
            old = []
    seen = {(x["mid"], x["bvid"]) for x in old}
    merged = old + [m for m in manifest if (m["mid"], m["bvid"]) not in seen]
    mpath.write_text(json.dumps({"generated": time.time(), "stats": stats,
                                 "items": merged}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    if b.logged_in:
        b.persist_cred()
    print(f"\n[stats] {stats}", file=sys.stderr)
    print(f"[out] {a.outroot}\\{a.platform}   用时 {time.time()-t0:.0f}s",
          file=sys.stderr)


if __name__ == "__main__":
    main()
