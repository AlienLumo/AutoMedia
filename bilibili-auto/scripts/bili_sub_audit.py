#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_sub_audit.py — 检查已采视频的字幕缺失，并可按需补下。

用途
  B站深采时用了 --sub-langs zh，只会保存含 zh 的字幕；有些视频当时没有
  AI 字幕、或只有别的语种，就会留下没有 subtitle.* 的目录。本脚本重新
  查一次 x/player/wbi/v2，判断"当年是真没有"还是"有但我们没下"。

分类
  no_subtitle : 接口返回的字幕列表为空（B站确实没有字幕）
  no_zh       : 有字幕，但没有 zh 语种（例如只有 ai-en）
  missing_lang: 有 zh 字幕，但目录里没落盘 → 可用 --fix 补下
  error       : 请求/解析异常

用法
  python bili_sub_audit.py --limit 30                 # 抽样 30 个看分布
  python bili_sub_audit.py --limit 0 --fix            # 全量检查并补下
  python bili_sub_audit.py --workers 1 --pace 1.3
"""
import argparse
import json
import sys
import time
from pathlib import Path
from _paths import PROJECT

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, Throttled, Budget, read_cred, to_srt  # noqa: E402

PROJ = PROJECT
DATA = PROJ / "1AMdata" / "bilibili"
STATE_DIR = PROJ / "1AMdata" / "_state"
OUT = STATE_DIR / "sub_audit.json"


def has_subtitle(vdir: Path) -> bool:
    for p in vdir.iterdir():
        if p.is_file() and p.name.lower().startswith("subtitle."):
            return True
    return False


def scan_missing():
    """返回 [(updir, vdir, meta)]，只含没有 subtitle.* 的视频目录。"""
    out = []
    for updir in sorted(DATA.iterdir()):
        if not updir.is_dir():
            continue
        for vdir in sorted(updir.iterdir()):
            if not vdir.is_dir() or vdir.name.startswith("_"):
                continue
            if has_subtitle(vdir):
                continue
            meta_p = vdir / "meta.json"
            if not meta_p.exists():
                continue
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not meta.get("aid") or not meta.get("cid"):
                continue
            out.append((updir, vdir, meta))
    return out


def langs_of(lan: str):
    return [t for t in (lan or "zh").lower().replace("_", "-").split("-") if t]


def audit_one(b, updir, vdir, meta, fix):
    aid, cid = meta["aid"], meta["cid"]
    try:
        r = b.get("x/player/wbi/v2", {"aid": aid, "cid": cid})
    except (Throttled, Budget):
        raise
    except Exception as e:
        return "error", f"{type(e).__name__}: {e}", 0

    subs = (((r.get("data") or {}).get("subtitle")) or {}).get("subtitles") or []
    if not subs:
        return "no_subtitle", "", 0

    zh_subs = [s for s in subs if "zh" in langs_of(s.get("lan"))]
    if not zh_subs:
        return "no_zh", ",".join(sorted({s.get("lan") or "?" for s in subs})), 0

    if not fix:
        return "missing_lang", ",".join(sorted({s.get("lan") or "?" for s in zh_subs})), 0

    saved = 0
    for s in zh_subs:
        url = s.get("subtitle_url") or ""
        if url.startswith("//"):
            url = "https:" + url
        if not url:
            continue
        try:
            data = b._raw(url)
        except Exception:
            continue
        body = data.get("body") or []
        if not body:
            continue
        lan = (s.get("lan") or "zh").replace("/", "_")
        (vdir / f"subtitle.{lan}.srt").write_text(to_srt(body), encoding="utf-8")
        (vdir / f"subtitle.{lan}.txt").write_text(
            "\n".join((x.get("content") or "").strip() for x in body),
            encoding="utf-8")
        saved += 1
        time.sleep(b.pace)
    return ("fixed" if saved else "missing_lang"), "", saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=30, help="0 = 全部")
    ap.add_argument("--fix", action="store_true", help="把有 zh 字幕但缺失的补下")
    ap.add_argument("--pace", type=float, default=1.3)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    missing = scan_missing()
    print(f"无字幕的视频目录总数: {len(missing)}", flush=True)
    todo = missing if a.limit == 0 else missing[: a.limit]
    print(f"本次检查: {len(todo)}", flush=True)

    b = Bili(pace=a.pace, cooldown=120, cookies=read_cred())
    stat = {}
    rows = []
    for i, (updir, vdir, meta) in enumerate(todo, 1):
        try:
            verdict, detail, saved = audit_one(b, updir, vdir, meta, a.fix)
        except Throttled:
            print("throttled, stop", flush=True)
            stat["throttled"] = stat.get("throttled", 0) + 1
            break
        except NotLoggedInLike as e:  # pragma: no cover
            print(f"login problem: {e}", flush=True)
            break
        stat[verdict] = stat.get(verdict, 0) + 1
        rows.append({
            "up": updir.name, "video": vdir.name, "bvid": meta.get("bvid"),
            "verdict": verdict, "detail": detail, "saved": saved,
        })
        if i % 10 == 0:
            print(f"  {i}/{len(todo)} {stat}", flush=True)

    print("\n=== 汇总 ===")
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    Path(a.out).write_text(
        json.dumps({"total_missing": len(missing), "checked": len(rows),
                    "stat": stat, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"\n明细已写入 {a.out}")


class NotLoggedInLike(Exception):
    pass


if __name__ == "__main__":
    main()
