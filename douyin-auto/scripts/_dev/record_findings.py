# -*- coding: utf-8 -*-
"""把抖音链路的验证结论写入 skills/进度.md。"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _paths import SKILL

P = SKILL.parent / "进度.md"
txt = P.read_text(encoding="utf-8")

add = """
## 2026-11-02 20:45 抖音链路：隔离验证第一轮（关键结论）

**环境已验证**（`AutoMedia/douyin-auto/scripts/`）：
- 项目内 Python 3.12.14 + **patchright**（Playwright 反检测分支）+ Chromium 1208，
  用 `runtime/python/python.exe` 启动，独立 profile
  `data/social/douyin-verify-profile`（未与主号共用）。
- 扫码登录**一次成功**，登录态已持久化到 profile：重启后仍 `登录=True`（cookie 含
  sessionid / sessionid_ss / sid_tt / uid_tt / passport_assist_user）。
- 首页 `https://www.douyin.com/` 可正常加载，无验证。

**硬约束（实测）**：
1. **headless 完全不可用**——无头模式访问首页/搜索页均被下发「验证码中间页」。
   抖音自动化必须全程有头（需要桌面会话）。
2. **搜索页风控极严**：本会话连续约 5 次自动页面访问（搜索→主页→搜索）后，
   搜索页开始返回验证码；而**首页仍正常**，账号未被封。说明是页面级挑战，不是封号。
3. 正常页面会常驻一个**隐藏的 captcha iframe**（反爬 SDK 预加载），
   不能用「元素存在」判定验证码，必须判可见性/标题。

**技术要点**：
- 搜索页用户链接为协议相对 `//www.douyin.com/user/MS4wLjABAAAA...`，需补 `https:`；
  `/user/self` 是自己的主页，须过滤；短 id 是残缺链接，须丢弃。
- 搜索页（type=user）能直接解析出：昵称 / 抖音号 / 获赞 / 粉丝 / 简介。
- `data-e2e="scroll-list"` 是结果容器。

**结论**：抖音与 B站 的可行性完全不同。B站 可连续跑两天、每轮 500 请求；
抖音约 5 次页面访问即触发挑战。因此「持续监测数百个博主」在自动化路径上**不可行**，
需要重新定范围（见下）。

**待用户决策**：
- A. 极低频只监控少量核心博主（5–10 个，每小时 1–2 个主页）；
- B. 半自动：遇验证码暂停，人工过一次后继续；
- C. 改用第三方数据平台（新榜/飞瓜）取数，零账号风险；
- D. 暂缓抖音，只做 B站。

**未验证**：主页作品列表提取（首轮访问被搜索页验证码阻断）、逐字稿 ASR、
图像/视频下载、sk_ill 化封装。
"""

if "2026-11-02 20:45 抖音链路" not in txt:
    P.write_text(txt.rstrip() + "\n" + add, encoding="utf-8")
    print("skills/进度.md 已写入抖音验证结论")
else:
    print("已存在，跳过")

