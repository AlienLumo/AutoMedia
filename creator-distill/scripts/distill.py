# -*- coding: utf-8 -*-
"""distill.py — 博主蒸馏统一入口（平台无关）。

用法：
  python distill.py --platform xiaohongshu --creator "鹏鹏有个想法" --detail 3 --frames 4
  python distill.py --platform xiaohongshu --creator "..." --no-asr --max-works 20

产出：1AMdata/distill/<platform>/<creator>/{creator.json, works/, report.md}
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from scripts._paths import OUT_ROOT  # noqa: E402
from distill.report import build_report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="xiaohongshu",
                    choices=["xiaohongshu", "bilibili", "douyin"])
    ap.add_argument("--creator", required=True)
    ap.add_argument("--max-works", type=int, default=30, dest="max_works")
    ap.add_argument("--detail", type=int, default=3, help="下载/ASR/抽帧的作品数")
    ap.add_argument("--frames", type=int, default=4)
    ap.add_argument("--no-asr", action="store_false", dest="asr", default=True)
    ap.add_argument("--no-frames", action="store_false", dest="frame", default=True)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--reuse", action="store_true",
                    help="复用已有 creator.json（不重新抓取，仅重算报告）")
    ap.add_argument("--out-root", default=str(OUT_ROOT), dest="out_root")
    a = ap.parse_args()

    out_dir = Path(a.out_root) / a.platform / a.creator
    out_dir.mkdir(parents=True, exist_ok=True)

    data_file = out_dir / "creator.json"
    if a.reuse and data_file.exists():
        import json
        data = json.loads(data_file.read_text(encoding="utf-8"))
        if a.platform == "xiaohongshu":
            from adapters.xiaohongshu import clean_title, is_reupload
            for w in data.get("works") or []:
                w["title"] = clean_title(w.get("title"))
                tr = (w.get("transcript") or {}).get("text") or ""
                if tr:
                    w["likely_reupload"] = is_reupload(tr)
        print(f"[reuse] {data_file}", file=sys.stderr)
    elif a.platform == "xiaohongshu":
        from adapters import xiaohongshu as adapter
        data = adapter.fetch(a.creator, out_dir, max_works=a.max_works,
                             detail_works=a.detail, with_asr=a.asr,
                             with_frames=a.frame, frames=a.frames,
                             headless=not a.headful)
    else:
        print(f"{a.platform} adapter 尚未实现（schema 已就绪）", file=sys.stderr)
        return 3

    report, md = build_report(data, out_dir)
    print(md)
    print(f"\n[report] {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
