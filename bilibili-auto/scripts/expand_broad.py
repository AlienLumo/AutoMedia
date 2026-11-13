# -*- coding: utf-8 -*-
"""expand_broad.py — B站账号级宽搜（按新口径：商业含财经/局势/炒股/科技/创客/科普）。

与 expand_accounts.py 的区别：
  - 商业 并入 财经（宏观经济/产业链/财报等），词量从 21 扩到 ~120
  - 局势/炒股/科技 大幅扩充
  - 数码评测单独一组，后续只取 Top5
  - 不在这里做 AI 相关度过滤（交给分类阶段按主题分别处理）

输出 config/candidates_broad.tsv：mid 名称 粉丝 主题 命中词 简介
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
OUT = CONF / "candidates_broad.tsv"

GROUPS = {
    "商业": [
        # 创业与生意
        "创业", "创业者", "创业故事", "创业项目", "创业经验", "创业失败", "小微创业",
        "实体创业", "小生意", "摆摊", "开店", "加盟", "连锁", "餐饮创业", "实体店",
        "门店经营", "店铺运营",
        # 副业与个人商业
        "副业", "副业赚钱", "睡后收入", "被动收入", "自由职业",
        "一人公司", "超级个体", "独立开发者", "独立产品", "个人IP", "知识付费",
        "内容变现", "出海", "跨境电商", "独立站", "DTC",
        # 商业分析
        "商业分析", "商业模式", "商业思维", "商业逻辑", "商业变现", "生意经",
        "赚钱思维", "案例拆解", "商业案例", "公司分析", "企业经营", "战略",
        "竞争壁垒", "营销", "品牌", "私域", "流量运营", "用户增长", "获客",
        # ===== 财经（并入商业）=====
        "宏观经济", "经济形势", "经济周期", "通胀", "通缩", "加息", "降息",
        "货币政策", "财政政策", "利率", "汇率", "美联储", "央行", "国债",
        "债务危机", "产业分析", "产业链", "供应链", "制造业", "半导体产业",
        "芯片产业", "房地产", "楼市", "房价", "城镇化", "人口", "内需", "外贸",
        "关税", "贸易战", "财报解读", "财报分析", "上市公司", "估值", "并购",
        "破产", "暴雷", "中概股", "财经解读", "财经知识", "经济学", "经济学思维",
        "看懂财经", "金融知识", "理财科普",
    ],
    "局势": [
        "国际局势", "世界局势", "地缘政治", "国际关系", "地缘", "大国博弈",
        "世界格局", "中美关系", "中美博弈", "俄乌", "俄乌冲突", "中东", "巴以",
        "台海", "南海", "朝鲜半岛", "军事", "武器装备", "国防", "军力对比",
        "战争分析", "军事科普", "时政", "时事", "时政评论", "国际新闻",
        "全球热点", "外交", "联合国", "北约", "欧盟", "金砖", "一带一路",
        "近代史", "历史解读",
    ],
    "炒股投资": [
        "炒股", "股票", "股市", "A股", "港股", "美股", "科创板", "创业板",
        "北交所", "价值投资", "趋势投资", "技术分析", "量化交易", "短线",
        "基金", "指数基金", "ETF", "债券", "可转债", "期权", "期货", "黄金",
        "原油", "外汇", "投资理财", "资产配置", "复利", "财务自由", "养老金",
        "保险", "个股分析", "选股", "龙头股", "板块", "题材",
    ],
    "科技": [
        "前沿科技", "科技趋势", "未来科技", "科技革命", "科技突破", "技术突破",
        "量子计算", "量子通信", "核聚变", "可控核聚变", "超导", "光刻机",
        "芯片制造", "脑机接口", "基因编辑", "合成生物", "新材料", "储能",
        "光伏", "氢能", "固态电池", "航天", "SpaceX", "星舰", "商业航天",
        "深空探测", "科技产业", "硬科技", "半导体", "算力", "数据中心",
        "新能源汽车", "智能汽车", "自动驾驶", "机器人产业", "工业机器人",
        "人形机器人", "科技公司", "科技巨头", "产业观察", "科技观察",
        "科技解读", "技术解析", "硬核科技", "科技科普", "原理讲解",
    ],
    "创客": [
        "自制机器人", "DIY机器人", "开源硬件", "单片机", "树莓派", "Arduino",
        "ESP32", "电路设计", "PCB", "机械臂", "机器狗", "嵌入式", "3D打印",
        "电子制作", "硬件开发", "开源项目", "GitHub项目", "创客", "极客",
    ],
    "科普": [
        "硬核科普", "科普", "知识科普", "科学知识", "科学实验", "技术解读",
    ],
    "数码评测": [
        "数码评测", "手机评测", "电脑评测", "开箱评测",
    ],
}


def load_known():
    mids = set()
    p = CONF / "ups.tsv"
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        try:
            mids.add(int(line.split("\t")[0]))
        except ValueError:
            pass
    return mids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", default="")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--min-fans", type=int, default=10000, dest="min_fans")
    ap.add_argument("--pace", type=float, default=1.4)
    ap.add_argument("--cooldown", type=int, default=90)
    ap.add_argument("--budget", type=int, default=0)
    a = ap.parse_args()

    picked = [g.strip() for g in a.groups.split(",") if g.strip() in GROUPS] \
        if a.groups else list(GROUPS)

    b = Bili(pace=a.pace, cooldown=a.cooldown, time_budget=a.budget,
             cookies=read_cred())
    b.preflight()
    known = load_known()

    hits = defaultdict(lambda: {"name": None, "fans": 0, "sign": "",
                                "kws": set(), "groups": set()})
    total = sum(len(GROUPS[g]) * a.pages for g in picked)
    done = 0

    for g in picked:
        for kw in GROUPS[g]:
            for page in range(1, a.pages + 1):
                done += 1
                try:
                    r = b.get("x/web-interface/wbi/search/type",
                              {"search_type": "bili_user", "keyword": kw,
                               "page": page, "order": "fans"}, tries=2)
                except (Throttled, Budget) as e:
                    print(f"[STOP] {kw}: {e}", file=sys.stderr)
                    raise SystemExit(2)
                except Exception as e:
                    print(f"  ! {kw} p{page}: {str(e)[:60]}", file=sys.stderr)
                    continue
                res = (r.get("data") or {}).get("result") or []
                for u in res:
                    mid = u.get("mid")
                    fans = u.get("fans") or 0
                    if not mid or fans < a.min_fans:
                        continue
                    e = hits[mid]
                    e["name"] = u.get("uname") or e["name"]
                    e["fans"] = fans
                    e["sign"] = (u.get("usign") or "").replace("\n", " ")[:120]
                    e["kws"].add(kw)
                    e["groups"].add(g)
                if done % 30 == 0:
                    print(f"  [{g}] {kw} p{page}: {len(res)} | 累计 {len(hits)} "
                          f"| {done}/{total}", file=sys.stderr)
                time.sleep(b.pace)

    rows = []
    for mid, e in hits.items():
        rows.append({"mid": mid, "name": e["name"], "fans": e["fans"],
                     "groups": sorted(e["groups"]), "kws": sorted(e["kws"]),
                     "sign": e["sign"], "in_roster": mid in known})
    rows.sort(key=lambda x: -x["fans"])

    with OUT.open("w", encoding="utf-8") as f:
        f.write("mid\t名称\t粉丝\t主题\t命中词\t简介\t已在名单\n")
        for r in rows:
            f.write(f'{r["mid"]}\t{r["name"]}\t{r["fans"]}\t'
                    f'{",".join(r["groups"])}\t'
                    f'{",".join(r["kws"][:6])}\t{r["sign"]}\t'
                    f'{"是" if r["in_roster"] else "否"}\n')

    new = [r for r in rows if not r["in_roster"]]
    print(f"\n完成：候选 {len(rows)}（名单外 {len(new)}）→ {OUT}")
    by_g = defaultdict(int)
    for r in rows:
        for g in r["groups"]:
            by_g[g] += 1
    print("按主题:", dict(by_g))
    print("\n名单外 Top 25：")
    for r in new[:25]:
        print(f'  {r["fans"]/1e4:>8.1f}万  {r["name"][:20]:<22} '
              f'[{",".join(r["groups"])}]')


if __name__ == "__main__":
    main()
