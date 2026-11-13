# -*- coding: utf-8 -*-
"""sample_resume.py — B站候选的「视频采样核验」，支持断点续跑。

对每个候选抓最近 20 个视频标题，算主题词占比：
  ≥40%  收录
  15-40% 待复核
  <15%  淘汰

关键设计（防 B站 风控）：
  - 每批最多 N 次请求（默认 350），跑完自动退出、保存进度
  - 被风控（v_voucher/Throttled）立即停止并保存
  - 再次运行自动从上次中断处继续

用法：
  python sample_resume.py --input config/final_roster_new.tsv --budget 350
  python sample_resume.py --input config/final_roster_new.tsv --report   # 只出报告
"""
import argparse
import json
import sys
import time
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget  # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"
PROGRESS = CONF / "sample_progress.json"

TOPIC_WORDS = {
    "商业": ["创业", "生意", "商业", "赚钱", "副业", "开店", "加盟", "营收",
             "利润", "公司", "企业", "经营", "营销", "品牌", "变现", "财报",
             "估值", "上市", "并购", "产业链", "供应链", "制造", "出海",
             "跨境", "经济", "通胀", "利率", "美联储", "央行", "汇率",
             "房价", "楼市", "人口", "消费", "外贸", "关税", "财经", "投资",
             "生意经", "小本", "摆摊", "门店"],
    "局势": ["局势", "地缘", "国际", "中美", "俄乌", "中东", "巴以", "台海",
             "南海", "朝鲜", "军事", "武器", "国防", "战争", "时政", "时事",
             "外交", "联合国", "北约", "欧盟", "金砖", "大国", "格局", "历史"],
    "炒股投资": ["炒股", "股票", "股市", "A股", "港股", "美股", "基金",
                 "投资", "理财", "债券", "期权", "期货", "黄金", "原油",
                 "外汇", "价值投资", "量化", "选股", "财报", "估值"],
    "科技": ["科技", "前沿", "芯片", "半导体", "量子", "核聚变", "光刻",
             "脑机", "基因", "新材料", "储能", "光伏", "氢能", "电池",
             "航天", "SpaceX", "星舰", "卫星", "算力", "大模型",
             "自动驾驶", "新能源", "机器人", "硬核", "原理", "科普"],
    "创客": ["创客", "自制", "DIY", "开源", "单片机", "树莓派", "Arduino",
             "ESP32", "电路", "PCB", "机械臂", "机器狗", "嵌入式", "3D打印",
             "电子制作", "极客", "硬件"],
    "数码评测": ["手机", "电脑", "笔记本", "开箱", "评测", "测评", "装机",
                 "显卡", "耳机", "相机", "数码"],
    "科普": ["科普", "原理", "科学", "知识"],
}

OFFTOPIC = ["美食", "探店", "吃播", "做饭", "菜谱", "零食",
            "搞笑", "段子", "沙雕", "游戏实况", "王者荣耀", "原神",
            "舞蹈", "翻唱", "cos", "鬼畜", "萌宠", "育儿"]


def load_progress():
    if PROGRESS.exists():
        try:
            return json.loads(PROGRESS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_progress(p):
    PROGRESS.write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")


def read_input(path):
    rows = []
    for ln in Path(path).read_text(encoding="utf-8").splitlines()[1:]:
        if not ln.strip():
            continue
        c = ln.split("\t")
        if len(c) < 5:
            continue
        try:
            rows.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "prefix": c[3], "tier": c[4]})
        except ValueError:
            continue
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(CONF / "final_roster_new.tsv"))
    ap.add_argument("--budget", type=int, default=350)
    ap.add_argument("--pace", type=float, default=2.5)
    ap.add_argument("--cooldown", type=int, default=300)
    ap.add_argument("--samples", type=int, default=20)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    rows = read_input(a.input)
    prog = load_progress()
    pending = [r for r in rows if str(r["mid"]) not in prog]
    print(f"待核验 {len(pending)}/{len(rows)}（已完成 {len(prog)}）")

    if a.report:
        ok = [k for k, v in prog.items() if v.get("verdict") == "ok"]
        mid = [k for k, v in prog.items() if v.get("verdict") == "mid"]
        bad = [k for k, v in prog.items() if v.get("verdict") == "bad"]
        print(f"  收录 {len(ok)} / 待复核 {len(mid)} / 淘汰 {len(bad)}")
        return

    if not pending:
        print("全部核验完成")
        return

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget, cookies=read_cred())
    b.preflight()

    n = 0
    for r in pending:
        if n >= a.budget:
            print(f"已达本批上限 {a.budget}，保存并退出")
            break
        try:
            resp = b.get("x/space/wbi/arc/search",
                         {"mid": r["mid"], "ps": a.samples, "pn": 1,
                          "order": "pubdate"}, tries=2)
        except (Throttled, Budget) as e:
            print(f"[STOP] {type(e).__name__}: {str(e)[:80]}")
            break
        except Exception as e:
            msg = str(e)[:60]
            print(f"  ! {r['name']}: {msg}", file=sys.stderr)
            prog[str(r["mid"])] = {"verdict": "err", "msg": msg}
            save_progress(prog)
            n += 1
            continue

        data = resp.get("data") or {}
        if "v_voucher" in data or not data:
            print("[STOP] 触发风控（v_voucher）")
            break

        vlist = (data.get("list") or {}).get("vlist") or []
        titles = [(v.get("title") or "") for v in vlist]
        n += 1
        if not titles:
            prog[str(r["mid"])] = {"verdict": "err", "msg": "no titles"}
            save_progress(prog)
            continue

        text = " ".join(titles)
        words = TOPIC_WORDS.get(r["prefix"], [])
        hit = sum(1 for t in titles if any(w in t for w in words))
        off = sum(1 for t in titles if any(w in t for w in OFFTOPIC))
        ratio = hit / len(titles)
        if ratio >= 0.4 and off <= len(titles) * 0.3:
            verdict = "ok"
        elif ratio >= 0.15:
            verdict = "mid"
        else:
            verdict = "bad"
        prog[str(r["mid"])] = {
            "mid": r["mid"], "name": r["name"], "fans": r["fans"],
            "prefix": r["prefix"], "tier": r["tier"],
            "ratio": round(ratio, 2), "hit": hit, "n": len(titles),
            "off": off, "verdict": verdict,
            "sample": titles[0][:60] if titles else "",
        }
        save_progress(prog)
        if n % 20 == 0:
            ok = sum(1 for v in prog.values() if v.get("verdict") == "ok")
            print(f"  {n}/{a.budget}  已收录 {ok}  最新: {r['name'][:14]} "
                  f"占比{ratio:.2f}", flush=True)

    ok = sum(1 for v in prog.values() if v.get("verdict") == "ok")
    mid = sum(1 for v in prog.values() if v.get("verdict") == "mid")
    bad = sum(1 for v in prog.values() if v.get("verdict") == "bad")
    print(f"\n本批 {n} 次请求。累计：收录 {ok} / 复核 {mid} / 淘汰 {bad}")
    print(f"进度文件: {PROGRESS}")


if __name__ == "__main__":
    main()
