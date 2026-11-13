# -*- coding: utf-8 -*-
"""为每个事件生成 README.md（事件摘要+素材清单）与 文案素材.md（口播/标题/金句/观点）。"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_paths import day_dir, DATE, day_iso

BASE = day_dir()

E = {
"01_anthropic-ipo": {
 "title": "Anthropic IPO：目标估值最高 1.4 万亿美元，AI 风险写进招股书",
 "summary": [
   "Anthropic 正式启动 IPO：发行区间对应公司估值最高 1.4 万亿美元，按 8.25 亿股、每股 70–78 美元计算，募资规模最高约 643.5 亿美元，有望成为史上最大 IPO 之一。",
   "招股材料罕见地把「AI 可能对人类构成生存性风险」写进风险披露；同时英伟达计划在 IPO 同期投资 100 亿美元，谷歌与亚马逊作为早期股东将获得巨额账面收益。",
   "对散户而言，这是第一次能通过 Schwab、Fidelity、Robinhood、E-Trade、SoFi 等券商直接买到头部 AI 公司股票。",
 ],
 "timeline": ["11-09：更新 S-1，确定发行区间（8250 万股、70–78 美元/股）", "11-10：路透/彭博/Deadline 集中报道，估值上限 1.4 万亿美元", "11-10：英伟达被曝计划投资 100 亿美元", "11-11：中文媒体大面积跟进（IT之家早报等）"],
 "numbers": ["估值上限：1.4 万亿美元", "发行：8.25 亿股 × 70–78 美元", "募资上限：约 643.5 亿美元", "英伟达拟投：100 亿美元"],
 "quotes": ["「AI 可能构成人类生存性风险」——招股书风险披露", "「万亿 IPO 来了，但散户本来可以更早拥有 AI 股票」——CNBC"],
 "hooks": ["一家公司估值 1.4 万亿美元，却在招股书里说自己的技术可能毁灭人类。",
           "AI 史上最大 IPO 来了：散户第一次能直接买万亿 AI 公司。",
           "英伟达一边卖铲子，一边给挖金子的人投 100 亿美元。"],
 "titles": ["1.4 万亿！Anthropic 把「人类风险」写进了招股书",
            "史上最大 AI IPO：散户终于能买了",
            "英伟达投 100 亿，Anthropic 的万亿故事怎么讲"],
 "points": ["资本视角：这是 AI 泡沫的试金石——定价能否撑住 1.4 万亿，决定一级市场估值体系。",
            "产业视角：英伟达投资客户，等于把「卖铲子」升级成「持股矿场」。",
            "风险视角：招股书自己写「生存性风险」，说明监管与治理会成为估值变量。"],
 "risks": ["1.4 万亿为区间上限，最终定价可能下修；Bloomberg/NYT 原文被付费墙拦截，数字以 Deadline/CNBC/IT之家交叉为准。"],
},
"02_anthropic-office": {
 "title": "Anthropic 杀入办公：Claude 白板/表格/数据 + Meetings，正面挑战微软",
 "summary": [
   "Anthropic 推出 Claude Whiteboards（白板）、Claude Sheets（表格）、Claude Data（仪表盘/数据故事），把 Claude 从「聊天问答」推进到团队协作工作台；Whiteboards 与 Sheets 处于测试，Data 已正式上线，面向所有付费计划。",
   "同期上线 Claude Meetings：把会议讨论自动整理成计划与任务；Claude 也已进入 Google Meet。",
   "The Verge 的判断：这是 IPO 前争夺白领用户的关键一步，直接对标 Microsoft 365/Google Workspace。",
 ],
 "timeline": ["11-10：The Verge、Bloomberg 报道办公套件", "11-10：TechCrunch 报道 Claude Meetings", "11-11：IT之家中文详解（白板/表格/数据三件套）"],
 "numbers": ["3 件套：Whiteboards / Sheets / Data", "覆盖端：网页 + 桌面 + 移动", "付费计划：全部可用（白板/表格测试中）"],
 "quotes": ["「从生成文字、代码或文档，转向直接参与团队日常协作」——官方定位", "「这是 IPO 前争夺白领用户的关键一步」——The Verge"],
 "hooks": ["Anthropic 不只想做模型，它开始抢微软的办公桌了。",
           "Claude 现在能开白板、做表格、出数据看板——办公三件套齐了。",
           "AI 办公战争开打：微软、谷歌、Anthropic 三方正面撞车。"],
 "titles": ["Claude 办公三件套上线，微软慌不慌？",
            "Anthropic 杀进 Office：白板、表格、数据全都有",
            "AI 办公战争：为什么 Anthropic 要在 IPO 前抢白领"],
 "points": ["产品视角：办公套件是「工作流入口」，比聊天窗口更容易锁定企业客户。",
            "商业视角：IPO 前需要「收入故事」，办公订阅是最可讲的部分。",
            "竞争视角：微软 Copilot 有分发优势，Anthropic 有模型口碑，胜负看企业迁移成本。"],
 "risks": ["白板/表格仍在测试；Bloomberg 原文付费墙，细节以 The Verge/TechCrunch/IT之家为准。"],
},
"03_claude-52": {
 "title": "Claude Fable 5.2 / Mythos 5.2 发布：编程登顶、速度 +30%、价格 -20%",
 "summary": [
   "Anthropic 发布 Claude Fable 5.2 与 Claude Mythos 5.2：编码、推理、科研、网络安全、机器人能力显著提升，输出速度最高 +30%、成本 -20%。",
   "定价：每百万 Token 输入 8 美元、输出 40 美元（Fable 5.1 为 10/50 美元），是「能力更强、价格更便宜」的组合拳。",
   "官方演示称 8 天从零搓出操作系统；中文媒体称其在编程上超过 GPT-6 Astra、登顶多项基准。",
 ],
 "timeline": ["11-10：官方发布 Fable 5.2 / Mythos 5.2", "11-10：IT之家报道能力与定价", "11-11：中文圈持续发酵"],
 "numbers": ["速度 +30%", "成本 -20%", "输入 $8 / 输出 $40 每百万 Token（较 5.1 的 $10/$50 下降）"],
 "quotes": ["「能力更强、价格更便宜」——这次发布的核心信号", "「8 天从零搓出操作系统」——官方演示"],
 "hooks": ["更强还更便宜：Claude 5.2 把价格战打到了自己身上。",
           "编程登顶、速度 +30%、价格 -20%——这一次 Anthropic 没留余地。",
           "8 天从零写出一个操作系统，AI 编程的边界又往前挪了。"],
 "titles": ["Claude 5.2 发布：更强、更快、更便宜",
            "编程登顶！Claude Fable 5.2 全面解析",
            "价格战开打：Anthropic 把 API 降价 20%"],
 "points": ["竞争视角：前沿模型进入「能力+价格」双维度竞争。",
            "应用视角：成本下降 20% 会直接改变 Agent 产品的毛利模型。",
            "基准视角：编程/科研/安全是三大高频付费场景。"],
 "risks": ["「超过 GPT-6 Astra」为媒体转述，需以官方基准为准。"],
},
"04_gemini4-carbon": {
 "title": "Google 发布 Gemini 4 Carbon：最强模型 + Agent Swarm + 两款新 TPU",
 "summary": [
   "谷歌正式开放 Gemini 4 Carbon，称其为迄今最强模型，主打复杂编程、科学研究与网络安全，面向开发者、企业、科研人员和消费者。",
   "新模型带「agent swarm」能力；谷歌同时联合 Artificial Analysis 推出 MKA（多模态知识智能体）基准，Gemini 4 Carbon 排名第二，任务成本仅为第一名的 1/6。",
   "同一天谷歌推出两款新 TPU，继续加码与英伟达的算力竞争；Android 开发者基准也首次公开 GPT-6.1 Terra、Kimi K3.1 Pro、DeepSeek V4.1 Flash 等成绩。",
 ],
 "timeline": ["11-10：Gemini 4 Carbon 开放、MKA 基准发布", "11-10：两款新 TPU 发布", "11-11：IT之家/钛媒体中文跟进"],
 "numbers": ["MKA 基准：Gemini 4 Carbon 第二", "任务成本：第一名的 1/6", "新 TPU：两款"],
 "quotes": ["「面向复杂编程、科学研究与网络安全」——官方定位", "「任务成本仅为第一名六分之一」——MKA 基准"],
 "hooks": ["谷歌一天发三样：最强模型、新基准、两款 TPU。",
           "能力第二、成本只有 1/6——谷歌这次打的是性价比。",
           "模型、基准、芯片一起发，谷歌在重建 AI 全栈。"],
 "titles": ["Gemini 4 Carbon 发布：谷歌的最强一击",
            "成本只有 1/6：谷歌用性价比挑战第一名",
            "模型+基准+TPU：谷歌的全栈反击"],
 "points": ["全栈视角：模型、评测标准、芯片同时推进，是谷歌的差异化。",
            "成本视角：MKA 基准强调「任务成本」，说明企业采购更看重单位任务价格。",
            "竞争视角：TPU 正面硬刚英伟达，算力价格战继续。"],
 "risks": ["Verge 原文被反爬截断，细节以 IT之家/钛媒体为准；Benchmark 名次需看官方榜单。"],
},
"05_alibaba-qwen-tpu": {
 "title": "阿里三线并进：Qwen4 预告、Qwen Code 1.0 开源、平头哥赴港 IPO",
 "summary": [
   "阿里官宣新一代千问大模型 Qwen4 即将发布（知识理解、世界感知、Coding 与 Agentic 能力进阶），预览版已首发上线。",
   "Qwen Code 1.0 发布：Qoder 与 Qwen Code 融合开源，Harness 统一衔接模型、工具与执行过程。",
   "芯片子公司平头哥（T-Head）拟赴港交所 IPO，已于 9 月 11 日保密递表；CNBC 称其为「英伟达的挑战者」。",
 ],
 "timeline": ["09-11：平头哥保密递表港交所", "11-11：阿里官宣 Qwen4 预告与 Qwen Code 1.0", "11-11：CNBC 报道平头哥 IPO 计划"],
 "numbers": ["平头哥：已保密递表", "阿里港股：当日跌约 1%，年内跌约 29%", "Qwen Code：1.0 版本"],
 "quotes": ["「知识理解更深入，世界感知更立体」——Qwen4 官方预告", "「英伟达的挑战者」——CNBC 对平头哥的定位"],
 "hooks": ["同一天，阿里把模型、代码工具、芯片 IPO 三件事一起推了。",
           "Qwen4 要来了，平头哥也要上市了：阿里在打一套组合拳。",
           "从模型到芯片，中国 AI 的「全栈叙事」正在成形。"],
 "titles": ["Qwen4 预告 + 平头哥 IPO：阿里三线并进",
            "阿里 AI 全栈：模型、工具、芯片一起上",
            "平头哥赴港 IPO，阿里芯片业务要独立了？"],
 "points": ["战略视角：模型（Qwen）+ 工具（Qwen Code）+ 芯片（平头哥）+ 云，是全栈打法。",
            "资本视角：平头哥 IPO 会把中国 AI 芯片的估值锚摆到台面上。",
            "生态视角：Qwen Code 开源，抢的是开发者默认工具链。"],
 "risks": ["Qwen4 仍是「即将发布」，参数未公布；平头哥 IPO 尚在流程中。"],
},
"06_openai-business": {
 "title": "OpenAI 商业化加速：ChatGPT 商家资料 + 收购 Odessia 做旅行 Agent",
 "summary": [
   "OpenAI 推出「Businesses in ChatGPT」：商家可以认领/创建资料，ChatGPT 内直接展示商家信息，并面向美国电商企业提供 AI Agent 投放能力。",
   "TechCrunch 评价：这让 ChatGPT 更像 Google——从「回答问题」转向「发现+交易」。",
   "OpenAI 还收购了 AI 旅行智能体公司 Odessia，创始人 Francis Davidson 加入，探索旅游方向的 Agent。",
 ],
 "timeline": ["11-10：OpenAI 发布 Businesses in ChatGPT", "11-10：TechCrunch/Investing 报道商家资料与 Agent 投放", "11-11：IT之家报道收购 Odessia"],
 "numbers": ["入口：ChatGPT 内商家资料", "市场：先面向美国电商企业", "收购：Odessia（AI 旅行智能体）"],
 "quotes": ["「让 ChatGPT 更像 Google」——TechCrunch", "「帮助 OpenAI 探索旅游业务方向」——Odessia 创始人"],
 "hooks": ["ChatGPT 开始卖货了：商家资料 + Agent 投放一起上。",
           "OpenAI 不想只做聊天工具，它要做一个「AI 版搜索+电商入口」。",
           "收购旅行 Agent 公司，OpenAI 在给 Agent 找真实场景。"],
 "titles": ["ChatGPT 变 Google？OpenAI 的商业化野心",
            "商家资料 + Agent 投放：OpenAI 开始做流量生意",
            "OpenAI 收购 Odessia：Agent 落地旅游场景"],
 "points": ["商业视角：广告/商家资料是 ChatGPT 最现实的变现路径。",
            "产品视角：从会话到「发现-比较-交易」闭环，入口价值放大。",
            "Agent 视角：收购垂直 Agent 团队，补齐行业 know-how。"],
 "risks": ["商家资料与广告能力目前主要面向美国市场，中国区影响有限。"],
},
"07_nvidia-huang": {
 "title": "英伟达「黄仁勋传闻」发酵：治理与地缘风险被摆上台面",
 "summary": [
   "CNBC 评论文章称，围绕英伟达 CEO 黄仁勋的「中国间谍」指控，暴露的不只是个人问题，而是科技行业、资本市场与政治领导层的系统性失灵。",
   "Tom's Hardware 援引 The Information 调查：Alice Huang 被指在三年关系中协助超过 75 亿美元的英伟达 AI GPU 进入中国，涉及约 24 万颗被禁芯片（多为 H100/H200）。",
   "钛媒体晨报称「媒体：黄仁勋或被英伟达免职，尚未指定接班人」。以上均为媒体指控/传闻，英伟达与当事人尚未有最终结论。",
 ],
 "timeline": ["11-09/10：CNBC、The Information、Tom's Hardware 报道", "11-10：黄仁勋相关传闻扩散", "11-11：中文媒体跟进（钛媒体晨报）"],
 "numbers": ["涉事 GPU 进口：超 75 亿美元", "被禁芯片：约 24 万颗（H100/H200 为主）", "传闻：或面临免职（未证实）"],
 "quotes": ["「这不是一个人的失败，而是行业、市场和政治领导层的失败」——CNBC 评论", "「英伟达最大风险，正在从供应转向治理」——本库判断"],
 "hooks": ["英伟达最大的风险，可能不是芯片，而是 CEO。",
           "24 万颗被禁芯片、75 亿美元：一桩传闻把英伟达推上风口。",
           "如果黄仁勋真的离开，英伟达还值多少钱？"],
 "titles": ["黄仁勋传闻背后：英伟达的治理风险",
            "24 万颗芯片、75 亿美元：英伟达被调查传闻",
            "英伟达的「CEO 风险」被市场定价了吗"],
 "points": ["治理视角：创始人 CEO 与公司深度绑定，是估值溢价也是单点风险。",
            "地缘视角：出口管制与灰色渠道，会持续扰动供应链叙事。",
            "市场视角：传闻未证实前，股价反应往往先于事实。"],
 "risks": ["涉及个人名誉与未证实指控，文案必须用「据报道/传闻/被指」，不得下结论；避免使用当事人照片与未经核实细节。"],
},
"08_ai-market-rout": {
 "title": "AI 市场回调：OpenAI/Anthropic 估值回落，基金以史上最快速度抛售科技股",
 "summary": [
   "Bloomberg 报道：随着 AI 市场回调冲击融资，OpenAI 与 Anthropic 的估值出现回落；对冲基金正以史上最快的速度之一抛售全球科技股。",
   "但二级市场分化明显：费城半导体指数涨 2.67%，博通、AMD、应用材料涨超 6%，而英伟达逆势跌 5.89%。",
   "一边是一级市场估值降温，一边是芯片股反弹——资本正在从「讲故事」转向「看兑现」。",
 ],
 "timeline": ["11-09：Bloomberg 报道估值回落与抛售", "11-10：对冲基金抛售、芯片股分化", "11-11：中文媒体跟进"],
 "numbers": ["费半：+2.67%", "博通 +6.25% / AMD +6.12% / 应用材料 +6.94%", "英伟达：-5.89%"],
 "quotes": ["「估值回落，融资遇冷」——Bloomberg", "「资本从抢筹转向看兑现」——本库判断"],
 "hooks": ["AI 估值开始松动了：一级市场降温，二级市场却在分化。",
           "同一天：芯片股大涨，英伟达却跌了 6%。",
           "当对冲基金用史上最快速度抛售科技股，谁在接盘？"],
 "titles": ["AI 估值回调：泡沫开始挤了吗",
            "芯片股大涨、英伟达下跌：市场在分化什么",
            "一级降温、二级分化：AI 资本走到哪一步了"],
 "points": ["资本视角：一级估值与二级股价背离，说明市场开始区分「故事」与「现金流」。",
            "结构视角：算力链（芯片/设备）仍被看好，模型公司估值承压。",
            "风险视角：若 IPO 定价下修，整个 AI 一级市场会重估。"],
 "risks": ["Bloomberg 原文付费墙；数据以东方财富/钛媒体为准，市场数据有滞后。"],
},
"09_meta-muse": {
 "title": "Meta 轻量模型 Muse Ember：100 万上下文、成本 1/3，还上了 Apple Watch",
 "summary": [
   "Meta 推出迄今最小、最高效模型 Muse Ember：100 万 Token 上下文、最多输出 51.2 万 Token，跑分媲美 Claude Haiku 5.5，单任务成本仅约 1/3。",
   "定价极低：输入 $0.10 / 输出 $0.50 每百万 Token，已在 Meta Model API、Google Cloud、Oracle Cloud 提供。",
   "同时 Meta 的 AI 助手 Muse 登陆 Apple Watch，入口从手机扩展到可穿戴。",
 ],
 "timeline": ["11-10：Muse Ember 发布", "11-11：IT之家中文报道", "11-11：Muse 登陆 Apple Watch 报道"],
 "numbers": ["上下文：100 万 Token", "最大输出：51.2 万 Token", "价格：$0.10 / $0.50 每百万 Token", "成本：约 1/3"],
 "quotes": ["「迄今最小、效率最高」——Meta", "「单任务成本仅 1/3」——IT之家"],
 "hooks": ["100 万上下文、成本只有 1/3：Meta 开始打「效率战」。",
           "最便宜的旗舰级模型来了，价格低到 0.1 美元/百万 Token。",
           "Meta 的 AI 助手，悄悄上了你的 Apple Watch。"],
 "titles": ["Meta Muse Ember：便宜到离谱的高效模型",
            "100 万上下文 + 1/3 成本：Meta 的效率战",
            "AI 助手登陆 Apple Watch，Meta 抢入口"],
 "points": ["成本视角：模型价格进入「分钱级」，Agent 大规模部署成为可能。",
            "入口视角：可穿戴是下一块屏幕，Meta 提前卡位。",
            "竞争视角：开源/低价模型正在挤压闭源高价模型的空间。"],
 "risks": ["跑分对比为厂商口径，需第三方基准验证。"],
},
"10_apple-ai-quota": {
 "title": "苹果限制 Apple Intelligence 云端额度：AI 算力开始「按量收费」",
 "summary": [
   "苹果支持文档显示：部分依赖服务器端模型的 Apple Intelligence 功能将受使用限制，涉及 Siri AI、图乐园、照片智能编辑，以及快捷指令中的 AFM 3 Cloud / AFM 3 Cloud Pro。",
   "用户可通过订阅 iCloud+ 扩容；Logic Pro 已单独售卖用量包。",
   "这意味着：连苹果也开始把「云端 AI 算力」当成需要计价的资源。",
 ],
 "timeline": ["11-11：苹果支持文档与媒体报道", "11-11：IT之家中文解读"],
 "numbers": ["受限功能：Siri AI / 图乐园 / 照片智能编辑 / 快捷指令云端模型", "扩容方式：iCloud+ 订阅", "另售：Logic Pro 用量包"],
 "quotes": ["「部分依赖服务器端模型的功能将受到使用限制」——苹果支持文档"],
 "hooks": ["苹果也开始对 AI 限额度了：云端算力，真的要按量付费。",
           "iCloud+ 不只是存照片，现在还能「买 AI 用量」。",
           "当 AI 变成云服务，免费额度终有一天会用完。"],
 "titles": ["苹果 AI 开始限额：云端算力按量收费",
            "iCloud+ 能买 AI 额度了，苹果的算力生意",
            "免费 AI 的时代，正在结束"],
 "points": ["商业视角：AI 推理成本显性化，订阅分层成为必然。",
            "产品视角：限制云端功能，会推动端侧模型与本地算力。",
            "趋势视角：从「免费无限」到「按量计费」，AI 进入基础设施化阶段。"],
 "risks": ["具体额度与地区差异未公布，以苹果官方支持文档为准。"],
},
}


def main():
    index = []
    for slug, ev in E.items():
        d = BASE / slug
        d.mkdir(parents=True, exist_ok=True)
        links = json.loads((d / "links.json").read_text(encoding="utf-8")) if (d / "links.json").exists() else []
        ok = [m for m in links if m.get("chars", 0) > 200]
        fail = [m for m in links if m.get("chars", 0) <= 200]
        off = len(list((d / "原文").glob("官方动态_*.md")))

        readme = [f"# {ev['title']}", "",
                  f"> 事件目录：`1信息源/{DATE}/{slug}/` ｜ 抓取时间：{day_iso()} ｜ 原文 {len(ok)} 篇 / 链接 {len(links)} 个", "",
                  "## 一、事件摘要", ""]
        readme += [f"- {p}" for p in ev["summary"]]
        readme += ["", "## 二、时间线", ""] + [f"- {t}" for t in ev["timeline"]]
        readme += ["", "## 三、关键数字", ""] + [f"- {n}" for n in ev["numbers"]]
        readme += ["", "## 四、素材清单（原文）", "", "| 标签 | 状态 | 正文字数 | 链接 | 本地文件 |", "|---|---|---|---|---|"]
        for m in links:
            st = "✅" if m.get("chars", 0) > 200 else "❌"
            readme.append(f"| {m['label']} | {st} {m.get('status')} | {m.get('chars',0)} | {m['url']} | {m.get('file','-')} |")
        if fail:
            readme += ["", "**缺口（付费墙/反爬，未取到正文）**："]
            readme += [f"- {m['label']}：{m['url']}（{m.get('status')}）" for m in fail]
        official = sorted(p.name for p in (d / "原文").glob("官方动态_*.md"))
        if official:
            readme += ["", "**官方动态页（补充素材）**："] + [f"- `原文/{o}`" for o in official]
        shots = sorted((d / "截图").glob("*")) if (d / "截图").exists() else []
        vids = sorted((d / "录屏").glob("*.mp4")) if (d / "录屏").exists() else []
        if shots or vids:
            readme += ["", "## 五、视觉素材", "",
                       f"- 截图 {len(shots)} 张（`截图/`）：整页长图、标题区、滚动分镜、页面大图",
                       f"- 录屏 {len(vids)} 条（`录屏/`）：页面滚动视频，可直接做画中画/B-roll", ""]
            if shots:
                readme.append("**截图清单**：")
                readme += [f"- `截图/{s.name}`" for s in shots]
            if vids:
                readme.append("**录屏清单**：")
                readme += [f"- `录屏/{v.name}`" for v in vids]
        readme += ["", "## 六、使用提示", "",
                   "- 原文存于 `原文/*.md`（已去标签），原始 HTML 存于 `raw/`；",
                   "- 文案素材见 `文案素材.md`；引用数字时请回原文核对；",
                   "- 付费墙来源仅能使用标题/摘要级信息。"]
        (d / "README.md").write_text("\n".join(readme), encoding="utf-8")

        clean = lambda s: str(s).rstrip("。；;，, ")
        draft = (f"{ev['hooks'][0]}\n\n"
                 f"先把事实说清楚：{clean(ev['summary'][0])}。{clean(ev['summary'][1])}。\n\n"
                 f"几个关键数字：{'；'.join(clean(n) for n in ev['numbers'][:3])}。\n\n"
                 f"我的判断是：{clean(ev['points'][0])}。{clean(ev['points'][1])}。\n\n"
                 f"关注「AI 前沿大事」，每天 60 秒，看懂 AI 前沿。")
        doc = [f"# 文案素材 · {ev['title']}", "", "## 一、60 秒口播草稿（画外音）", "", draft, "",
               "## 二、3 分钟长版结构", "",
               "1. 开场钩子（10 秒）：" + ev["hooks"][0],
               "2. 事实层（60 秒）：" + " ".join(clean(s) + "。" for s in ev["summary"][:2]),
               "3. 数据层（40 秒）：" + "；".join(clean(n) for n in ev["numbers"][:3]) + "。",
               "4. 判断层（50 秒）：" + " ".join(clean(p) + "。" for p in ev["points"][:2]),
               "5. 结尾 CTA（10 秒）：关注「AI 前沿大事」，明天继续。", "",
               "## 三、可复用钩子", ""] + [f"- {h}" for h in ev["hooks"]]
        doc += ["", "## 四、标题备选（抖音）", ""] + [f"- {t}" for t in ev["titles"]]
        doc += ["", "## 五、金句/引用", ""] + [f"- {q}" for q in ev["quotes"]]
        doc += ["", "## 六、数据点（可直接上字幕卡）", ""] + [f"- {n}" for n in ev["numbers"]]
        doc += ["", "## 七、观点角度", ""] + [f"- {p}" for p in ev["points"]]
        doc += ["", "## 八、风险与合规提示", ""] + [f"- {r}" for r in ev["risks"]]
        doc += ["- 所有数字须标注来源与日期；AI 生成画面需加「AI 生成」标识。"]
        (d / "文案素材.md").write_text("\n".join(doc), encoding="utf-8")

        index.append({"slug": slug, "title": ev["title"], "ok": len(ok) + off, "links": len(links)})

    idx = [f"# {day_iso()} 大事件素材库 · 索引", "",
           f"> 采集时间：{day_iso()} ｜ 事件 {len(index)} 个 ｜ 原文 {sum(i['ok'] for i in index)} 篇 / 链接 {sum(i['links'] for i in index)} 个 ｜ 视觉素材见各事件 `截图/`、`录屏/`", "",
           "| 目录 | 事件 | 原文 | 链接 | 截图 | 录屏 |", "|---|---|---|---|---|---|"]
    for i in index:
        d = BASE / i["slug"]
        ns = len(list((d / "截图").glob("*"))) if (d / "截图").exists() else 0
        nv = len(list((d / "录屏").glob("*.mp4"))) if (d / "录屏").exists() else 0
        idx.append(f"| [{i['slug']}]({i['slug']}/) | {i['title']} | {i['ok']} | {i['links']} | {ns} | {nv} |")
    idx += ["", "## 抓取缺口（付费墙/反爬，仅有标题/摘要级信息）", ""]
    gaps = []
    for slug in E:
        d = BASE / slug
        lj = d / "links.json"
        if not lj.exists():
            continue
        for m in json.loads(lj.read_text(encoding="utf-8")):
            if m.get("chars", 0) <= 200:
                gaps.append(f"- `{slug}` · {m['label']}：{m.get('status')} · {m['url']}")
    idx += (gaps or ["- 无"])
    people_dir = BASE / "关键人物"
    people = sorted(people_dir.glob("*.jpg")) + sorted(people_dir.glob("*.png")) if people_dir.exists() else []
    if people:
        idx += ["", "## 关键人物素材", "",
                f"- `关键人物/`：{len(people)} 张头像（来源 Wikipedia/Wikimedia，授权以各自来源 txt 标注为准）"]
        idx += [f"- `关键人物/{p.name}`" for p in people]
    idx += ["", "## 目录结构", "", "```", f"{DATE}/", "  <事件>/", "    README.md      事件摘要 + 时间线 + 关键数字 + 素材清单 + 视觉素材",
            "    文案素材.md    60秒口播 + 3分钟结构 + 钩子/标题/金句/数据/观点/风险",
            "    原文/*.md      抓取并清洗的正文（含官方动态页）", "    raw/*.html     原始 HTML", "    links.json     链接与抓取状态",
            "    截图/*.png|jpg 整页长图 / 标题区 / 滚动分镜 / 页面大图", "    录屏/*.mp4     页面滚动视频",
            "  关键人物/       人物头像（CC 授权，附来源）", "```"]
    (BASE / "README.md").write_text("\n".join(idx), encoding="utf-8")
    print("done:", len(index), "events")


if __name__ == "__main__":
    main()
