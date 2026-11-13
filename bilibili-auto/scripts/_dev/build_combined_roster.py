# -*- coding: utf-8 -*-
"""build_combined_roster.py — 合并「视频搜索候选」+「账号搜索候选」，离线分配主题。

输入：
  config/candidates_video.tsv   (1153 个，含粉丝+视频标题)
  config/candidates_broad.tsv   (785 个，含粉丝+命中词+简介)
输出：
  config/combined_roster.tsv    (待采样核验的候选，含主题/层级)
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

CONF = SKILL / "config"

# 主题词（标题/简介/命中词任一命中即计）
RULES = {
    "商业": ["创业", "生意", "商业", "赚钱", "副业", "开店", "加盟", "营收",
             "利润", "公司", "企业", "经营", "营销", "品牌", "变现", "财报",
             "估值", "上市", "并购", "产业链", "供应链", "制造", "出海",
             "跨境", "经济", "GDP", "通胀", "利率", "美联储", "央行", "汇率",
             "房价", "楼市", "人口", "消费", "外贸", "关税", "财经", "投资",
             "生意经", "小本", "摆摊", "门店", "财报解读", "商业模式"],
    "局势": ["局势", "地缘", "国际关系", "中美", "俄乌", "中东", "巴以",
             "台海", "南海", "朝鲜", "军事", "武器", "国防", "战争", "时政",
             "时事", "外交", "联合国", "北约", "欧盟", "金砖", "一带一路",
             "大国博弈", "世界格局", "历史"],
    "炒股投资": ["炒股", "股票", "股市", "A股", "港股", "美股", "基金",
                 "投资", "理财", "债券", "期权", "期货", "黄金", "原油",
                 "外汇", "价值投资", "量化", "选股"],
    "科技": ["前沿科技", "科技趋势", "未来科技", "芯片", "半导体", "量子",
             "核聚变", "光刻", "脑机", "基因编辑", "合成生物", "新材料",
             "储能", "光伏", "氢能", "电池", "航天", "SpaceX", "星舰",
             "卫星", "算力", "数据中心", "大模型", "自动驾驶", "新能源",
             "机器人", "硬核", "原理", "科技科普"],
    "创客": ["创客", "自制", "DIY", "开源硬件", "单片机", "树莓派",
             "Arduino", "ESP32", "电路", "PCB", "机械臂", "机器狗",
             "嵌入式", "3D打印", "电子制作", "极客", "硬件开发"],
    "数码评测": ["数码评测", "手机评测", "电脑评测", "开箱评测"],
}

HARD_INST = ["央视", "中央电视", "CCTV", "CNTV", "人民日报", "人民网", "新华社",
             "新华网", "共青团", "观察者网", "环球时报", "澎湃", "界面新闻",
             "财新", "第一财经", "中国网", "中国日报", "光明网", "经济日报",
             "参考消息", "环球网", "政府", "国务院", "外交部", "国防部",
             "卫健委", "教育部", "央行", "证监会", "卫视", "广电", "广播电台",
             "电视台", "日报", "晚报", "晨报", "新闻网", "全国妇联", "科协",
             "红十字会", "研究院", "研究所", "大学", "学院"]
SOFT_INST = ["集团", "公司", "商城", "官方", "频道", "传媒", "文化传播",
             "协会", "基金会", "科技有限", "出版社", "杂志", "报社"]
PERSONAL_HINT = ["老师", "老", "哥", "姐", "叔", "阿姨", "同学", "小明",
                 "阿", "小", "先生", "博士", "教授", "UP主"]

OFFTOPIC = ["美食", "探店", "吃播", "做饭", "菜谱", "零食",
            "搞笑", "段子", "沙雕", "游戏实况", "王者荣耀", "原神",
            "舞蹈", "翻唱", "cos", "鬼畜", "萌宠", "育儿"]


def is_personal(name):
    n = name or ""
    if any(w in n for w in HARD_INST):
        return False
    if any(w in n for w in SOFT_INST):
        return any(w in n for w in PERSONAL_HINT)
    return True


def load_video():
    rows = []
    p = CONF / "candidates_video.tsv"
    if not p.exists():
        return rows
    for ln in p.read_text(encoding="utf-8").splitlines()[1:]:
        c = ln.split("\t")
        if len(c) < 6:
            continue
        try:
            rows.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "kws": [k for k in c[3].split(",") if k],
                         "text": " ".join(c[3].split(",")) + " " + c[4],
                         "in_roster": c[5] == "是", "src": "video"})
        except ValueError:
            continue
    return rows


def load_broad():
    rows = []
    p = CONF / "candidates_broad.tsv"
    if not p.exists():
        return rows
    for ln in p.read_text(encoding="utf-8").splitlines()[1:]:
        c = ln.split("\t")
        if len(c) < 7:
            continue
        try:
            rows.append({"mid": int(c[0]), "name": c[1], "fans": int(c[2]),
                         "kws": [k for k in c[4].split(",") if k],
                         "text": " ".join(c[3].split(",")) + " " + c[4] + " " + c[5],
                         "in_roster": c[6] == "是", "src": "account"})
        except ValueError:
            continue
    return rows


def main():
    v = load_video()
    b = load_broad()
    print(f"视频搜索候选 {len(v)}，账号搜索候选 {len(b)}")

    merged = {}
    for r in v + b:
        if r["mid"] in merged:
            # 合并文本 + 取较高粉丝
            m = merged[r["mid"]]
            m["text"] += " " + r["text"]
            m["kws"] = list(dict.fromkeys(m["kws"] + r["kws"]))
            m["fans"] = max(m["fans"], r["fans"])
            m["src"] = m["src"] + "+" + r["src"]
        else:
            merged[r["mid"]] = dict(r)
    print(f"合并去重后 {len(merged)} 个")

    out = []
    skip_inst = skip_off = skip_roster = 0
    for m in merged.values():
        if m["in_roster"]:
            skip_roster += 1
            continue
        if not is_personal(m["name"]):
            skip_inst += 1
            continue
        if any(w in m["text"] for w in OFFTOPIC):
            skip_off += 1
            continue
        # 分配主题：取得分最高的
        best, best_score = None, 0
        for prefix, words in RULES.items():
            s = sum(1 for w in words if w in m["text"])
            if s > best_score:
                best, best_score = prefix, s
        if not best or best_score < 2:
            continue
        # 数码评测特殊处理（后面只取 Top5）
        m["prefix"] = best
        m["score"] = best_score
        m["tier"] = "A" if m["fans"] >= 100000 else "B"
        out.append(m)

    out.sort(key=lambda x: (x["prefix"], -x["fans"]))
    tsv = CONF / "combined_roster.tsv"
    with tsv.open("w", encoding="utf-8", newline="") as f:
        f.write("mid\t名称\t粉丝\t前缀\t层级\t得分\t来源\n")
        for m in out:
            f.write(f'{m["mid"]}\t{m["name"]}\t{m["fans"]}\t{m["prefix"]}\t'
                    f'{m["tier"]}\t{m["score"]}\t{m["src"]}\n')

    from collections import Counter
    print(f"\n跳过：已在名单 {skip_roster} / 机构号 {skip_inst} / 跑偏垂类 {skip_off}")
    print(f"入选待核验: {len(out)}")
    print("按前缀:", dict(Counter(m["prefix"] for m in out)))
    print("按层级:", dict(Counter(m["tier"] for m in out)))
    print(f"\n输出: {tsv}")
    print("\n各主题 Top 5:")
    for p in RULES:
        lst = [m for m in out if m["prefix"] == p][:5]
        if not lst:
            continue
        print(f"  [{p}]")
        for m in lst:
            print(f'    {m["fans"]/1e4:>8.1f}万  {m["name"][:20]:<22} 得分{m["score"]} {m["tier"]}')


if __name__ == "__main__":
    main()
