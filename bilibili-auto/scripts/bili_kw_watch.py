#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_kw_watch.py — 关键词轮询：按发布时间排序搜索，把「泛AI/科技/商业/硬件」的
新视频捞进收件箱（用于发现池外新内容与新号）。

用法：
  python bili_kw_watch.py --batch 60 --pages 2
  python bili_kw_watch.py --keywords "DeepSeek|AI Agent|具身智能" --pages 1

产出：
  - 新视频写入 1AMdata/watch/inbox.jsonl（source=kw, kw=命中词）
  - 状态 1AMdata/_state/watch/kw_state.json（轮换游标，保证所有词都能轮到）
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watch_common import (Client, Lock, Stop, add_inbox, ensure_dirs, emit, load_config,
                          load_index, load_json, load_known, load_roster, log,
                          looks_institutional, pace_sleep, NetLock, inline_collect,
                          save_json, STATE)

STATE_FILE = STATE / "kw_state.json"


def load_keywords(path):
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / p
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return list(dict.fromkeys(out))


def clean(t):
    for tag in ('<em class="keyword">', "</em>", "<em>", "</em>"):
        t = (t or "").replace(tag, "")
    return t.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keywords", default="", help="临时关键词，竖线分隔；空=用配置文件轮换")
    ap.add_argument("--batch", type=int, default=0, help="本轮处理多少个词")
    ap.add_argument("--pages", type=int, default=0)
    ap.add_argument("--days", type=int, default=0, help="只收最近 N 天发布的")
    ap.add_argument("--max-requests", type=int, default=0, dest="max_requests")
    ap.add_argument("--pace", type=float, default=0.0)
    ap.add_argument("--time-budget", type=int, default=900, dest="time_budget")
    ap.add_argument("--quiet", action="store_true", default=True)
    ap.add_argument("--no-quiet", action="store_false", dest="quiet")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ensure_dirs()
    cfg = load_config()
    kcfg = cfg["keywords"]
    all_kws = ([k.strip() for k in a.keywords.split("|") if k.strip()]
               if a.keywords else load_keywords(kcfg.get("file") or ""))
    if not all_kws:
        log("[kw] 关键词表为空，退出", "kw")
        return 1
    st = load_json(STATE_FILE, {"cursor": 0, "kw": {}})
    batch = a.batch or int(kcfg.get("batch_keywords") or 120)
    pages = a.pages or int(kcfg.get("pages") or 2)
    days = a.days if a.days else int(kcfg.get("days") or 3)
    per_kw_cap = int(kcfg.get("per_kw_cap") or 3)
    max_age_h = int(kcfg.get("max_age_hours") or 24)
    only_roster = bool(kcfg.get("only_roster", True))
    roster_mids = {u["mid"] for u in load_roster()} if only_roster else set()
    max_new = int(kcfg.get("max_new_per_run") or 300)
    max_req = a.max_requests or int(kcfg.get("max_requests_per_run") or 1200)

    # 轮换：从上次游标开始取一批，保证长尾词也能轮到
    n = len(all_kws)
    cur = int(st.get("cursor") or 0) % n
    kws = [all_kws[(cur + i) % n] for i in range(min(batch, n))]
    st["cursor"] = (cur + len(kws)) % n
    client = Client(pace=a.pace or cfg["pace_search"], max_requests=max_req,
                    quiet=a.quiet, time_budget=a.time_budget, tag="kw")
    log(f"[kw] 关键词 {len(kws)}/{n}（游标 {cur}）pages={pages} days={days} 开始", "kw")

    idx = load_index()
    try:
        known = load_known()
    except Exception:
        known = set()
    added, hits, requests0 = 0, 0, client.req
    inline_budget = int(kcfg.get("inline_cap_per_run") or 15)
    try:
        for kw in kws:
            for pn in range(1, pages + 1):
                try:
                    r = client.get("x/web-interface/wbi/search/type",
                                   {"search_type": "video", "keyword": kw,
                                    "page": pn, "order": "pubdate"})
                except Stop:
                    raise
                except Exception as e:
                    log(f"[err] kw={kw} p{pn}: {type(e).__name__}: {str(e)[:80]}", "kw")
                    break
                res = (r.get("data") or {}).get("result") or []
                if not res:
                    break
                items = []
                cutoff = time.time() - max_age_h * 3600
                k_norm = kw.lower().replace(" ", "")
                for v in res:
                    bvid = v.get("bvid")
                    if not bvid:
                        continue
                    pub = v.get("pubdate") or 0
                    if pub and pub < cutoff:
                        continue
                    author = v.get("author") or ""
                    if looks_institutional(author):
                        continue
                    if only_roster and (v.get("mid") not in roster_mids):
                        continue
                    title_c = clean(v.get("title"))
                    # 相关性：关键词必须出现在【标题】里（只命中标签会大量混入无关内容）
                    if k_norm not in title_c.lower().replace(" ", ""):
                        continue
                    items.append({"bvid": bvid, "mid": v.get("mid"), "up": author,
                                  "title": title_c,
                                  "play": v.get("play") or 0,
                                  "pubdate": pub, "source": "kw", "kw": kw})
                    if len(items) >= per_kw_cap:
                        break
                if items:
                    hits += len(items)
                    if a.dry_run:
                        for it in items:
                            log(f"[dry:{kw}] {it['up']} | {it['title'][:42]}", "kw")
                    else:
                        nac, newly = add_inbox(items, known=known)
                        added += nac
                        if kcfg.get("inline_subs", True) and inline_budget > 0:
                            for itx in newly[:inline_budget]:
                                inline_collect(client, itx)
                                inline_budget -= 1
                        for it in items:
                            if it["bvid"] not in idx:
                                log(f"[new:{kw}] {it['up']} | {it['title'][:42]}", "kw")
                        if added >= max_new:
                            raise Stop(f"达到本轮新增上限 {max_new}")
                pace_sleep(client, cfg["pace_search"])
            st["kw"][kw] = {"ts": int(time.time()), "hits": hits}
            save_json(STATE_FILE, st)
            if added and added % 200 == 0:
                log(f"[kw] 已收 {added} 条，请求 {client.req}", "kw")
    except Stop as e:
        log(f"[kw] 提前停止：{e}（游标已保存）", "kw")
    finally:
        save_json(STATE_FILE, st)
        client.close()
        summary = {"type": "kw_watch", "keywords": len(kws), "raw_hits": hits,
                   "new": added, "requests": client.req - requests0}
        emit(summary)
        log(f"[kw] 完成：{summary}", "kw")
    return 0


if __name__ == "__main__":
    with Lock("kw"), NetLock(wait=300, tag="kw"):
        raise SystemExit(main())










