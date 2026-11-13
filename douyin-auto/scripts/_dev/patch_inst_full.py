# -*- coding: utf-8 -*-
"""补全机构号关键词表 + 输出排除清单供复核。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

f = SKILL / "scripts" / "build_talk_queue.py"
t = f.read_text(encoding="utf-8")

start = t.index("HARD_INST = [")
end = t.index("# 按主题分组")

NEW = '''HARD_INST = [
    # 官方媒体
    "央视", "中央电视", "CCTV", "CNTV", "人民日报", "人民网", "新华社", "新华网",
    "共青团", "观察者网", "环球时报", "澎湃", "界面新闻", "财新", "第一财经",
    "中国网", "中国日报", "光明网", "经济日报", "参考消息", "环球网",
    "新闻网", "新闻", "报道", "日报", "晚报", "晨报", "周刊",
    "卫视", "广电", "广播电台", "电视台", "融媒体", "传媒",
    # 政府/机构
    "政府", "国务院", "外交部", "国防部", "卫健委", "教育部", "央行", "证监会",
    "全国妇联", "科协", "红十字会", "研究院", "研究所", "实验室",
    "清华", "北大", "大学", "学院", "中学", "小学",
    # 品牌/公司（抖音官方号）
    "华为", "小米", "苹果", "腾讯", "阿里", "百度", "字节", "京东", "美团",
    "特斯拉", "比亚迪", "蔚来", "理想汽车", "小鹏", "荣耀", "OPPO", "vivo",
    "三星", "英特尔", "英伟达", "联想", "戴尔", "微软", "谷歌", "Meta",
    "爱奇艺", "优酷", "芒果", "哔哩哔哩", "快手", "微博",
    "中国移动", "中国电信", "中国联通", "国家电网", "中石油", "中石化",
]
SOFT_INST = ["集团", "公司", "商城", "官方", "频道", "文化传播",
             "协会", "基金会", "科技有限", "出版社", "杂志", "报社",
             "影业", "娱乐", "文化", "工作室", "团队"]
PERSONAL_HINT = ["老师", "哥", "姐", "叔", "阿姨", "同学",
                 "先生", "博士", "教授", "UP主", "君", "叔", "爷", "妈", "爸"]


def is_personal(name):
    """判定是否个人自媒体。"""
    n = name or ""
    if any(w in n for w in HARD_INST):
        return False
    if any(w in n for w in SOFT_INST):
        return any(w in n for w in PERSONAL_HINT)
    return True


'''

t = t[:start] + NEW + t[end:]

# 输出排除清单
t = t.replace('''print(f"合并去重 {before} → 排除已采完后 {len(chosen)}")''',
'''print(f"合并去重 {before} → 排除已采完后 {len(chosen)}")

# 输出被排除的机构号供复核
inst_out = CFG / "excluded_institutions_douyin.tsv"
with inst_out.open("w", encoding="utf-8", newline="") as fh:
    fh.write("昵称\\t粉丝\\t主题\\n")
    for x in authors:
        th = [t2 for t2 in WANT if t2 in (x.get("themes") or [])]
        if not th or (x.get("fans") or 0) < a.min_fans:
            continue
        if not is_personal(x.get("nickname")):
            fh.write(f'{x.get("nickname")}\\t{x.get("fans")}\\t{",".join(th)}\\n')
print(f"排除的机构号清单: {inst_out}")''')

f.write_text(t, encoding="utf-8")
print("已补全机构词表 + 排除清单输出")
