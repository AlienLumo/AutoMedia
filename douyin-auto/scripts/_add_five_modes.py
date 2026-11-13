# -*- coding: utf-8 -*-
"""把 from_video.py / related.py 补进 douyin-auto SKILL.md。"""
from pathlib import Path
from _paths import SKILL

f = SKILL / "SKILL.md"
t = f.read_text(encoding="utf-8")

ADD = r'''

---

# 五种输入形态 → 对应命令（2026-11-07 补齐）

| 你的输入 | 要什么 | 命令 |
|---|---|---|
| **1. 领域名**（「找 AI 创业类的博主」）| 找号 | `douyin_find_by_video.py --themes <主题> --gap 360` |
| **2. 博主主页链接** | 采该博主全量 | `.\collect.ps1 -Link "<主页>"` |
| **3. 某条视频链接** | 反查作者 → 采他主页其他视频 | `python from_video.py --url "<视频>" --collect` |
| **4. 某条视频链接** | 找**同主题的其他视频** | `python related.py --url "<视频>"` |
| **5. 某条视频链接** | 找**同主题的其他博主** | `python related.py --url "<视频>" --min-fans 100000 --queue [--collect]` |

## ③ from_video.py（视频 → 作者 → 采集）

```powershell
python from_video.py --url "https://v.douyin.com/xxxx/"                  # 只解析作者
python from_video.py --url "https://v.douyin.com/xxxx/" --collect        # 解析并采集
python from_video.py --url "https://www.douyin.com/video/7623..." --collect --top-play 10 --latest 5
```

原理：打开视频页 → 拦截 `/aweme/detail/` → 取 `author.sec_uid` → 拼主页 URL → 交给 `douyin_collect.py`。

## ④⑤ related.py（视频 → 相关视频/博主）

```powershell
python related.py --url "https://v.douyin.com/xxxx/"                       # 列相关视频
python related.py --url "..." --rounds 3                                   # 扩散 3 轮（打开高赞相关视频继续挖）
python related.py --url "..." --min-fans 100000 --queue                    # 生成博主队列
python related.py --url "..." --min-fans 100000 --queue --collect          # 生成并采集
```

**原理（关键）**：抖音作品页会请求 `/aweme/v1/web/aweme/related/`，返回的 `aweme_list`
就是算法按内容相似度排好的「相关视频」，每条带作者与粉丝数。

**比关键词搜索更准** —— 算法已经做过语义匹配，不受关键词措辞影响。
`--rounds N` 会拿上一轮最高赞的相关视频当新种子，指数式扩散。

产出：
- `config/related_result.json`：相关视频（按点赞）+ ≥阈值的作者列表
- `config/queue_related.txt`：可直接喂给 `run_queue.ps1` 采集

## 组合用法示例

> 「这个视频不错，找一批同类型的博主都采了」

```powershell
python related.py --url "<视频链接>" --rounds 2 --min-fans 100000 --queue --collect
```

会自动：打开视频 → 挖相关视频 → 聚合作者 → 筛粉丝 → 逐个采集（每号 top10+latest5）。
'''

if "五种输入形态" not in t:
    t = t.rstrip() + ADD
    f.write_text(t, encoding="utf-8")
    print("已补入五种输入形态说明")
print(f"SKILL.md: {f.stat().st_size/1024:.1f} KB")
