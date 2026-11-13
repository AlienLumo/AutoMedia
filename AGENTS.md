# AutoMedia 项目入口（agent 用）

> 本仓库 = 四个只读采集/分析 skill 的合集。每个 skill 的详细用法看各自的 `SKILL.md`。
> 本文件只写：路由、硬约束、发布规则。

## 四个下属

| 目录 | 入口文档 | 一句话 |
|---|---|---|
| `bilibili-auto/` | `SKILL.md` → `README.md` | B站 UP 主批量采集 / 字幕 / 评论 / 监听 |
| `douyin-auto/` | `SKILL.md` → `README.md` | 抖音单账号采集 / 找号 / ASR |
| `creator-distill/` | `SKILL.md` | 对标博主蒸馏（schema v1，平台无关） |
| `news-source/` | `SKILL.md` | 资讯池 → 当日大事件素材库 |

## 开工顺序

1. 读根 `README.md` 的「快速开始」：`scripts/install.ps1` → `scripts/doctor.py`；
2. 读对应 skill 的 `SKILL.md`，再核对 `scripts/` 真实代码；
3. 运行前置（Python / Chromium / ffmpeg / 登录态）见根 `README.md` 与 `docs/安装与配置.md`；
4. 采集产出写 `1AMdata/` 或 `1信息源/<日期>/`，不写进本仓库；
5. 重要改动同步到工作区 `skills/` 与工作区文档。

## 工具与文档

| 路径 | 作用 |
|---|---|
| `scripts/install.ps1` | 安装/环境检查/链接到 DSH 工作区（支持 `-DryRun`） |
| `scripts/doctor.py` | 自检表（运行时/登录态/飞书/输出目录），`--json` 可机读 |
| `scripts/feishu_setup.py` | 飞书一键配置（自定义机器人 / 自建应用），可发测试消息 |
| `docs/安装与配置.md` | 环境变量、各 skill 配置、登录细节、故障排查 |
| `docs/常见问题.md` | 封号风险、磁盘占用、迁移、更新等 |
| `docs/assets/` | README banner 等图片资源 |

## 硬约束

- **只读**：不点赞/收藏/关注/评论/发布，不绕过验证码，不改平台账号资料。
- **凭据不入库**：`data/`、`credentials/`、cookie、浏览器 profile 一律不提交。
- **信息源链接不隐藏**：`news-source/config/sources.tsv`、`config/events/*.json`、示例里的链接原样保留。
- **脱敏**：本机绝对路径、用户名、邮箱、账号名、webhook/token 不出现；文档里用 `<项目根>` 等占位符。
- 单个采集实例串行运行，遵守各 skill 的间隔与限流规则。
