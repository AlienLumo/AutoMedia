#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_ups_watch.py — 盯住名单里的 UP 是否更新（只看最新几页投稿，增量入库）。

用法：
  python bili_ups_watch.py --tier S --max-requests 400
  python bili_ups_watch.py --tier A --max-requests 900
  python bili_ups_watch.py --tier all --dry-run --limit 20

产出：
  - 新视频写入 1AMdata/watch/inbox.jsonl（source=up）
  - 状态 1AMdata/_state/watch/ups_state.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watch_common import (Client, Lock, Stop, add_inbox, ensure_dirs, emit, load_config,
                          load_json, load_known, load_roster, log, inline_collect, pace_sleep, NetLock,
                          save_json, STATE)

STATE_FILE = STATE / "ups_state.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="all", help="S | A | B | all")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 个号（测试）")
    ap.add_argument("--max-requests", type=int, default=0, dest="max_requests")
    ap.add_argument("--max-new", type=int, default=0, dest="max_new")
    ap.add_argument("--pace", type=float, default=0.0)
    ap.add_argument("--time-budget", type=int, default=900, dest="time_budget")
    ap.add_argument("--quiet", action="store_true", default=True)
    ap.add_argument("--no-quiet", action="store_false", dest="quiet")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ensure_dirs()
    cfg = load_config()
    roster = load_roster()
    tier = a.tier.upper()
    ups = [u for u in roster if tier == "ALL" or u["tier"] == tier]
    if a.limit:
        ups = ups[:a.limit]
    if not ups:
        log(f"[ups] 没有匹配 tier={a.tier} 的账号", "watch")
        return 0

    st = load_json(STATE_FILE, {"ups": {}})
    st.setdefault("ups", {})
    st.setdefault("cursor", {})
    # 每轮从上次停下的位置继续，避免「预算用完就永远只查前 N 个号」
    cur = int(st["cursor"].get(tier) or 0) % len(ups)
    ups = ups[cur:] + ups[:cur]
    try:
        known = load_known()
    except Exception:
        known = set()
    first_hours = float(cfg["ups"].get("first_seen_hours") or 48)
    elastic_h = float(cfg["ups"].get("elastic_window_hours") or 48)
    lookback = int(cfg["ups"].get("incremental_lookback_sec") or 900)
    max_req = a.max_requests or cfg["ups"].get("max_requests_per_run", 1200)
    max_new = a.max_new or cfg["ups"].get("max_new_per_run", 60)
    ps = int(cfg["ups"].get("ps") or 5)
    client = Client(pace=a.pace or cfg["pace_list"], max_requests=max_req,
                    quiet=a.quiet, time_budget=a.time_budget, tag="ups")
    log(f"[ups] tier={tier} 账号={len(ups)} 上限请求={max_req} 开始", "ups")

    added_total, checked, errs, new_items = 0, 0, 0, []
    inline_budget = int(cfg["ups"].get("inline_cap_per_run") or 20)
    last_i = -1
    try:
        for i, u in enumerate(ups):
            last_i = i
            mid, name = u["mid"], u["name"]
            prev = st["ups"].get(str(mid)) or {}
            seen = set(prev.get("seen") or [])
            try:
                r = client.get("x/space/wbi/arc/search",
                               {"mid": mid, "ps": ps, "pn": 1, "order": "pubdate",
                                "platform": "web", "web_location": 1550101})
                vl = ((r.get("data") or {}).get("list") or {}).get("vlist") or []
                first_run = not prev.get("seen")
                now_ts = time.time()
                if first_run:
                    cutoff = now_ts - first_hours * 3600
                else:
                    # 弹性：优先收「上次检查之后」的，同时保底覆盖最近 elastic_hours 小时
                    cutoff = max((prev.get("checked") or 0) - lookback,
                                 now_ts - elastic_h * 3600)
                fresh = []
                for v in vl:
                    bvid = v.get("bvid")
                    if not bvid or bvid in seen:
                        continue
                    if (v.get("created") or 0) < cutoff:
                        continue
                    fresh.append(v)
                checked += 1
                if fresh:
                    items = [{"bvid": v["bvid"], "mid": mid, "up": name,
                              "title": v.get("title") or "",
                              "play": v.get("play") or 0,
                              "pubdate": v.get("created") or 0,
                              "source": "up", "tier": u["tier"],
                              "prefix": u["prefix"]} for v in fresh]
                    if a.dry_run:
                        for it in items:
                            log(f"[dry] {name} | {it['title'][:40]}", "ups")
                    else:
                        n, newly = add_inbox(items, known=known)
                        added_total += n
                        new_items.extend(items)
                        if cfg["ups"].get("inline_subs", True) and inline_budget > 0:
                            for itx in newly[:inline_budget]:
                                inline_collect(client, itx)
                                inline_budget -= 1
                        for it in items:
                            log(f"[new] {name} | {it['title'][:44]}", "ups")
                # 只保留最近 60 个 bvid，防止状态文件膨胀
                seen_list = [v.get("bvid") for v in vl if v.get("bvid")]
                merged = list(dict.fromkeys(list(seen) + seen_list))[-60:]
                st["ups"][str(mid)] = {"name": name, "seen": merged,
                                       "checked": int(time.time()),
                                       "last_pub": vl[0].get("created") if vl else None,
                                       "err": None}
                if added_total >= max_new:
                    log(f"[ups] 达到本轮新增上限 {max_new}，提前收工", "ups")
                    break
            except Stop:
                raise
            except Exception as e:
                errs += 1
                st["ups"][str(mid)] = {**(st["ups"].get(str(mid)) or {}),
                                       "err": f"{type(e).__name__}: {e}"[:160]}
                log(f"[err] {name}({mid}): {type(e).__name__}: {str(e)[:80]}", "ups")
            if (i + 1) % 50 == 0:
                save_json(STATE_FILE, st)
                log(f"[ups] 进度 {i+1}/{len(ups)} 请求={client.req} 新增={added_total} 错误={errs}", "ups")
            pace_sleep(client)
        if len(ups):
            st["cursor"][tier] = 0           # 完整跑完一轮，游标归零
    except Stop as e:
        if len(ups) and last_i >= 0:
            st["cursor"][tier] = (cur + last_i + 1) % len(ups)   # 从断点续跑
        log(f"[ups] 提前停止：{e}（游标已保存，下次从第 "
            f"{st['cursor'].get(tier, 0)} 个继续）", "ups")
    finally:
        save_json(STATE_FILE, st)
        client.close()
        summary = {"type": "ups_watch", "tier": tier, "checked": checked,
                   "errors": errs, "new": added_total, "requests": client.req}
        emit(summary)
        log(f"[ups] 完成：{summary}", "ups")
    return 0


if __name__ == "__main__":
    with Lock("ups"), NetLock(wait=300, tag="ups"):
        raise SystemExit(main())









