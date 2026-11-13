# -*- coding: utf-8 -*-
"""classify_sample.py — 视频采样分类（最终核验）。

对每个候选，抓取其最近 20 个视频标题，计算「主题词占比」：
  占比 ≥ 40% → 收录
  15%-40%   → 待人工复核
  < 15%     → 淘汰

这样能解决离线分类的误判（美食号偶尔发一条「开店」标题就被判成商业）。

用法（风控解除后）：
  python classify_sample.py --input final_roster_new.tsv --pace 2.5 --limit 400
"""
import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from _paths import PROJECT, SKILL

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bili_subs import Bili, read_cred, Throttled, Budget  # noqa: E402

PROJ = PROJECT
CONF = SKILL / "config"

# 各前缀的主题词（用于统计视频标题里的主题占比）
TOPIC_WORDS = {
    "商业": ["创业", "生意", "商业", "赚钱", "副业", "开店", "加盟", "营收",
             "利润", "公司", "企业", "经营", "营销", "品牌", "变现", "财报",
             "估值", "上市", "并购", "产业链", "供应链", "制造", "出海",
             "跨境", "经济", "GDP", "通胀", "利率", "美联储", "央行", "汇率",
             "房价", "楼市", "人口", "消费", "外贸", "关税", "财经", "投资"],
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
}

# 反向排除：出现这些说明是别的垂类
OFFTOPIC = ["美食", "探店", "吃播", "做饭", "菜谱", "测评零食",
            "搞笑", "段子", "沙雕", "游戏实况", "王者荣耀", "原神",
            "舞蹈", "翻唱", "cos", "鬼畜", "萌宠", "亲子", "育儿"]


def read_roster(path):
    rows = []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for ln in lines[1:]:
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
    ap.add_argument("--out", default=str(CONF / "final_roster_verified.tsv"))
    ap.add_argument("--pace", type=float, default=2.5)
    ap.add_argument("--cooldown", type=int, default=180)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--samples", type=int, default=20)
    a = ap.parse_args()

    rows = read_roster(a.input)[:a.limit]
    b = Bili(pace=a.pace, cooldown=a.cooldown, cookies=read_cred())
    b.preflight()
    print(f"待核验 {len(rows)} 个候选", flush=True)

    ok, mid, bad = [], [], []
    for i, r in enumerate(rows, 1):
        try:
            resp = b.get("x/space/wbi/arc/search",
                         {"mid": r["mid"], "ps": a.samples, "pn": 1,
                          "order": "pubdate"}, tries=2)
            vlist = ((resp.get("data") or {}).get("list") or {}).get("vlist") or []
        except (Throttled, Budget) as e:
            print(f"[STOP] {e}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  ! {r['name']}: {str(e)[:50]}", file=sys.stderr)
            continue

        titles = [(v.get("title") or "") for v in vlist]
        if not titles:
            continue
        text = " ".join(titles)
        words = TOPIC_WORDS.get(r["prefix"], [])
        hit = sum(1 for t in titles if any(w in t for w in words))
        off = sum(1 for t in titles if any(w in t for w in OFFTOPIC))
        ratio = hit / len(titles)
        r["ratio"] = round(ratio, 2)
        r["hit"] = hit
        r["n"] = len(titles)
        r["off"] = off
        r["sample"] = titles[0][:50] if titles else ""
        if ratio >= 0.4 and off <= len(titles) * 0.3:
            ok.append(r)
        elif ratio >= 0.15:
            mid.append(r)
        else:
            bad.append(r)
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}  收录 {len(ok)} 复核 {len(mid)} 淘汰 {len(bad)}",
                  flush=True)
        time.sleep(b.pace)

    out = Path(a.out)
    with out.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t前缀\t层级\t主题占比\t命中/样本\t跑偏\t样例标题\n")
        for group in (ok, mid):
            for r in group:
                f.write(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t{r["prefix"]}\t'
                        f'{r["tier"]}\t{r["ratio"]}\t{r["hit"]}/{r["n"]}\t'
                        f'{r["off"]}\t{r["sample"]}\n')

    print(f"\n结果：收录 {len(ok)} / 待复核 {len(mid)} / 淘汰 {len(bad)}")
    print(f"输出: {out}")
    from collections import Counter
    print("收录分布:", dict(Counter(r["prefix"] for r in ok)))
    print("\n淘汰样例（供确认误杀）：")
    for r in bad[:10]:
        print(f'  {r["name"][:20]:<22} [{r["prefix"]}] 占比{r["ratio"]}  {r["sample"][:30]}')


if __name__ == "__main__":
    main()
