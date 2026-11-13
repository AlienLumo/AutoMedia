#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_inbox_collect.py — 收件箱兜底：补字幕 / 补元数据（评论默认关闭）。

设计（2026-11-08 调整）：
- 跟踪任务（UP/关键词）已在发现时内联采集「元数据 + 中文逐字稿」，不采评论；
- 收件箱只做兜底：内联失败/未覆盖的补一次；无字幕的按 6h/24h/72h 重试；
- 发布不足 min_age_minutes 的视频先跳过（等字幕生成），下一轮再处理；
- 评论默认不采（config.inbox.with_comments=false），需要时加 --comments。

用法：
  python bili_inbox_collect.py --max-items 12
  python bili_inbox_collect.py --comments --max-items 5
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watch_common import (VIDEOS, Client, Lock, NetLock, Stop, ensure_dirs, emit,
                          load_config, load_json, log, pace_sleep, read_inbox,
                          safe_name, save_json, STATE)
from bili_collect import collect_comments, collect_meta, collect_subs

STATE_FILE = STATE / "processed.json"
RETRY_HOURS = [6, 24, 72]


def age_hours(meta):
    pub = meta.get("pubdate") or 0
    return (time.time() - pub) / 3600 if pub else 1e6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-items", type=int, default=0, dest="max_items")
    ap.add_argument("--max-requests", type=int, default=0, dest="max_requests")
    ap.add_argument("--comment-cap", type=int, default=0, dest="comment_cap")
    ap.add_argument("--nested-pages", type=int, default=1, dest="nested_pages")
    ap.add_argument("--comments", action="store_true", default=None, dest="comments")
    ap.add_argument("--no-comments", action="store_false", dest="comments")
    ap.add_argument("--min-age-minutes", type=int, default=-1, dest="min_age")
    ap.add_argument("--max-retries", type=int, default=-1, dest="max_retries")
    ap.add_argument("--pace", type=float, default=0.0)
    ap.add_argument("--time-budget", type=int, default=1800, dest="time_budget")
    ap.add_argument("--quiet", action="store_true", default=True)
    ap.add_argument("--no-quiet", action="store_false", dest="quiet")
    a = ap.parse_args()

    ensure_dirs()
    cfg = load_config()
    icfg = cfg["inbox"]
    max_items = a.max_items or int(icfg.get("max_items_per_run") or 12)
    max_req = a.max_requests or int(icfg.get("max_requests_per_run") or 400)
    cap = a.comment_cap or int(icfg.get("comment_cap") or 100)
    langs = [x.lower() for x in (icfg.get("sub_langs") or ["zh"])]
    if a.comments is None:
        a.comments = bool(icfg.get("with_comments", False))
    min_age = (a.min_age if a.min_age >= 0
               else int(icfg.get("min_age_minutes", 10)))
    max_retries = (a.max_retries if a.max_retries >= 0
                   else int(icfg.get("max_retries_per_run", 8)))
    ttl_days = int(icfg.get("backlog_ttl_days", 7))

    proc = load_json(STATE_FILE, {})
    items = read_inbox()
    now = time.time()
    pending, deferred, expired = [], 0, 0
    for it in items:
        bvid = it["bvid"]
        rec = proc.get(bvid) or {}
        if rec.get("status") in ("skipped", "expired"):
            continue
        if rec.get("status") == "done" and rec.get("sub", 0) > 0:
            continue
        if rec.get("status") == "done" and rec.get("cm"):
            continue
        if rec.get("status") == "done" and not rec.get("sub"):
            # 内联已试过、暂时没字幕：6 小时内不重复打，交给 retry 逻辑
            if now - int(rec.get("ts") or 0) < 6 * 3600:
                continue
        if rec.get("status") == "error" and rec.get("tries", 0) >= 2:
            continue
        dts = int(it.get("discovered_ts") or 0)
        if ttl_days and dts and (now - dts) > ttl_days * 86400:
            expired += 1
            proc[bvid] = {**(proc.get(bvid) or {}), "status": "expired",
                          "ts": int(now)}
            continue
        pub = it.get("pubdate") or 0
        if pub and (now - pub) < min_age * 60:
            deferred += 1
            continue
        pending.append(it)
    # UP 跟踪的优先，其次按发现时间倒序
    pending.sort(key=lambda x: (0 if x.get("source") == "up" else 1,
                                -int(x.get("discovered_ts") or 0)))
    pending = pending[:max_items]

    client = Client(pace=a.pace or cfg["pace_list"], max_requests=max_req,
                    quiet=a.quiet, time_budget=a.time_budget, tag="inbox")
    log(f"[inbox] 待处理 {len(pending)}（推迟 {deferred}，过期 {expired}，总收件箱 {len(items)}，"
        f"评论={'开' if a.comments else '关'}）", "inbox")
    done = errs = nsub = ncm = 0
    try:
        for i, it in enumerate(pending):
            bvid = it["bvid"]
            title = it.get("title") or bvid
            vdir = VIDEOS / f"{bvid}_{safe_name(title, 40)}"
            tries = int((proc.get(bvid) or {}).get("tries") or 0)
            try:
                if not (vdir / "meta.json").exists():
                    meta = collect_meta(client.b, {"bvid": bvid})
                    vdir.mkdir(parents=True, exist_ok=True)
                    meta.update({"source": it.get("source"), "kw": it.get("kw"),
                                 "tier": it.get("tier"), "prefix": it.get("prefix"),
                                 "discovered_at": it.get("discovered_at")})
                    meta["heat"] = round((meta.get("like") or 0) * 1.0
                                         + (meta.get("favorite") or 0) * 1.5
                                         + (meta.get("coin") or 0) * 2.0, 1)
                    (vdir / "meta.json").write_text(
                        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
                else:
                    meta = json.loads((vdir / "meta.json").read_text(encoding="utf-8"))
                csub = 0
                if not any(vdir.glob("subtitle.*.txt")):
                    try:
                        files, _ = collect_subs(client.b, meta["aid"], meta["cid"],
                                                vdir, "subtitle", langs)
                        csub = len(files)
                    except Stop:
                        raise
                    except Exception as e:
                        log(f"  ! subs {bvid}: {str(e)[:60]}", "inbox")
                ccm = 0
                if a.comments and not (vdir / "comments.jsonl").exists():
                    try:
                        cms = collect_comments(client.b, meta["aid"], cap, a.nested_pages)
                        with (vdir / "comments.jsonl").open("w", encoding="utf-8") as f:
                            for c in cms:
                                f.write(json.dumps(c, ensure_ascii=False) + "\n")
                        ccm = len(cms)
                    except Stop:
                        raise
                    except Exception as e:
                        log(f"  ! comments {bvid}: {str(e)[:60]}", "inbox")
                nsub += 1 if csub else 0
                ncm += ccm
                proc[bvid] = {"status": "done", "dir": vdir.name, "ts": int(time.time()),
                              "sub": csub, "cm": ccm, "tries": tries,
                              "pubdate": meta.get("pubdate"),
                              "sub_retries": 0, "source": "inbox"}
                done += 1
                log(f"[{i+1}/{len(pending)}] ok {bvid} 字幕={csub} 评论={ccm} 请求={client.req}",
                    "inbox")
            except Stop:
                raise
            except Exception as e:
                errs += 1
                proc[bvid] = {"status": "error", "ts": int(time.time()),
                              "err": f"{type(e).__name__}: {e}"[:160],
                              "tries": tries + 1, "dir": vdir.name}
                log(f"[err] {bvid}: {type(e).__name__}: {str(e)[:80]}", "inbox")
            if (i + 1) % 10 == 0:
                save_json(STATE_FILE, proc)
            pace_sleep(client)

        # ---- 无字幕重试：6h / 24h / 72h 各一次 ----
        retried = 0
        for bvid, rec in list(proc.items()):
            if retried >= max_retries:
                break
            if rec.get("status") != "done" or rec.get("sub"):
                continue
            n = int(rec.get("sub_retries") or 0)
            if n >= len(RETRY_HOURS):
                continue
            d = rec.get("dir")
            if not d:
                continue
            vdir = VIDEOS / d
            try:
                meta = json.loads((vdir / "meta.json").read_text(encoding="utf-8"))
            except Exception:
                continue
            if age_hours(meta) < RETRY_HOURS[n]:
                continue
            try:
                files, _ = collect_subs(client.b, meta["aid"], meta["cid"], vdir,
                                        "subtitle", langs)
                if files:
                    rec["sub"] = len(files)
                    retried += 1
                    log(f"[retry] {bvid} 补到字幕 {len(files)} 条", "inbox")
                rec["sub_retries"] = n + 1
                rec["last_retry"] = int(time.time())
                proc[bvid] = rec
            except Stop:
                raise
            except Exception as e:
                log(f"  ! retry subs {bvid}: {str(e)[:60]}", "inbox")
                rec["sub_retries"] = n + 1
                proc[bvid] = rec
            pace_sleep(client)
    except Stop as e:
        log(f"[inbox] 提前停止：{e}（已完成项已保存）", "inbox")
    finally:
        save_json(STATE_FILE, proc)
        client.close()
        summary = {"type": "inbox", "pending": len(pending), "deferred": deferred,
                   "expired": expired,
                   "done": done, "errors": errs, "with_sub": nsub,
                   "comments": ncm, "sub_retried": retried,
                   "requests": client.req}
        emit(summary)
        log(f"[inbox] 完成：{summary}", "inbox")
    return 0


if __name__ == "__main__":
    with Lock("inbox"), NetLock(wait=300, tag="inbox"):
        raise SystemExit(main())




