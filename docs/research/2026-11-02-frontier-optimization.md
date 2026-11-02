# 前沿调研：论文检索 Agent 与本系统优化方向

- **调研日期**：2026-11-02
- **调研人**：刘昆（与 AI 协作完成）
- **关联文档**：《中期检查报告_刘昆_SA23225270》、`docs/Agent_Design_Risk_Review.md`、`docs/Production_Concerns_RAG_Agents.md`
- **代码基线**：分支 `langgraph-inte`（工作树，2026-11-02）

## 0. 调研方法与可信度声明

- 本机环境下 WebSearch（Ark 控制台返回 403）与 dataPro 学术库（Agent Plan 席位失效）均不可用；改用可直连的 **OpenAlex 公共 API** 与 **arxiv.org 页面**核实。
- 附录文献表中每条标有**核实状态**：
  - ✅ OpenAlex 实测 = 题名、年份、venue、DOI 于 2026-11-02 经 OpenAlex API 实测（引用量亦为当日快照，会随时间变化）；
  - ✅ arXiv 页面核实 = 当日经 arxiv.org 页面核实；
  - ⚠️ 未独立核实 = OpenAlex 尚未收录且当日 arXiv 搜索被限流，仅按通行名称引用，**未给编号，正式写入论文前必须回源核对**。
- 代码现状判断基于当日工作树实际文件，而非报告描述（报告多处描述的是设计，实现仍是 stub）。
- 本文件是调研产物（spike），不构成实现设计；任何后续实现另走设计与评审流程。

---

## 1. 前沿地图：中期报告之后（或未覆盖）的重要进展

### 1.1 范式迁移：固定流水线 → 自适应 / 智能体检索（agentic RAG）

中期报告以 RAG（Lewis et al., NeurIPS 2020）+ ReAct（Yao et al., ICLR 2023）为底座。2024 年后该方向的主线是**让系统按需决定"是否检索、检索几次、检索失败怎么办"**：

- **Adaptive-RAG**（Jeong et al., NAACL 2024，当日 259 引用）：用问题复杂度分类器决定"不检索 / 单步检索 / 多步检索"，简单问题不付检索与 token 成本。直接对应中期报告 §4.2 后续工作中的"查询路由"。
- **CRAG（Corrective RAG）**（Yan et al., 2024，当日 182 引用）：检索后先过**检索质量评估器**，质量差则触发查询分解重写与兜底网络搜索。这是报告"低支撑自动补检索"想法的已发表范式。
- **Self-RAG**（Asai et al., ICLR 2024）：按需检索 + 逐句自我批评的反思 token 机制（报告 2.4 已引）。
- **FLARE**（Jiang et al., EMNLP 2023，499 引用）：生成过程中按置信度主动触发检索。
- **IRCoT**（Trivedi et al., ACL 2023，352 引用）：多跳问题上交替进行检索与思维链推理，每步检索用"问题+已有推理"改写。
- 综述视角：*Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG*（arXiv 2501.09136，2025，37 引用）；*Data-Centric Perspectives on Agentic RAG*（Findings of ACL 2026）。
- 2025–2026 训练式前沿（了解即可，本项目不建议实现）：**Search-R1**（arXiv 2503.09516）、**ReSearch**（NeurIPS 2025）、**R1-Searcher++**（arXiv 2505.17005）、**WebDancer**（NeurIPS 2025）、**WebSailor**（2025，⚠️ 未独立核实）以 RL 训练推理-搜索交错；**Reflective RAG**（Findings of ACL 2026）把"检索效用自评"引入 agentic 循环。

### 1.2 与本课题最像的系统：学术文献研究 Agent（中期报告 2.6 节缺失这一类，建议补入）

- **PaperQA / PaperQA2**：当前与本课题最接近的已发表系统。PaperQA（arXiv 2312.07559）是检索→证据片段→map-reduce 综合→带引用答案的科研生成式 Agent；PaperQA2（*Language agents achieve superhuman synthesis of scientific knowledge*，arXiv 2409.13740，2024）提出严格的人-机对比方法论，任务覆盖**信息检索、综述、矛盾检测**，论文标题级结论为"语言智能体在科研知识综合上达到超人水平"。
  - **答辩风险**：必然被问"你与 PaperQA2 的差异"。建议正面对位，差异化主张：结构化查询契约（UniRAG 式字段化）、多目标可解释重排（权威/时效/相关/多样按意图加权）、两级引用核验（L1 存在性 + L2 支撑性）、八阶段统一接口的可替换性、确定性流水线优先的有界 Agent（D2）。
- **ResearchAgent**（Baek et al., NAACL 2025，46 引用）：在科学文献上迭代"阅读→大纲→评审→修订"生成研究想法。
- **STORM**（Shao et al., NAACL 2024，41 引用）：多视角提问（multi-perspective question asking）先做主题研究与大纲，再写带引用的长文。综述生成阶段（Stage 6）的直接参照。
- **AutoSurvey**（Wang et al., NeurIPS 2024，25 引用）：递归展开大纲、分块并行生成综述。
- 2025 年后的综述生成工作：**SurveyForge / SurveyX**（⚠️ 编号未独立核实）、**SurveyG**（arXiv 2510.07733，2025，用层级引文图谱组织综述）、**DancerSurvey**（端到端 deep-research 综述 Agent，2025 预印本，⚠️ 未独立核实）、*Feedback Is The Key for Automated Survey Generation*（Findings of ACL 2026）。
- 相邻训练系统：**Aviary**（arXiv 2412.21154，2024，挑战性科研任务上的语言智能体训练）。

### 1.3 学术检索评测基准：报告只引了 LitSearch，2025–2026 已出现专门基准群

- **LitSearch**（Ajith et al., EMNLP 2024）：597 条真实文献检索查询，需要理解研究概念并跨整篇文章推理（报告 2.2 已引 ✓）。
- **SAGE**（arXiv 2602.05975，2026）：面向 deep research 工作流的**科学文献检索基准，1,200 条查询**，专门检验 LLM 检索器对研究类 Agent 的贡献。
- **AutoResearchBench**（arXiv 2604.25256，2026）：评测智能体完成复杂科学文献发现（为研究问题探索文献、为声明找证据）。
- **INSPIRE**（arXiv 2609.33233，2026）：从"开放研究问题"（而非已知目标论文）出发检索，设置晚于线索论文三个月的时间截止，按分级引用判定排名。
- **CompLit**（2026，覆盖 arXiv 全部 8 个领域，✅ OpenAlex 实测但无 DOI）：强调文献搜索的隐式需求（implicit）、累积式需求（cumulative）、未满足需求（unmet）。
- **PaperScope**（arXiv 2604.11307，2026）：海量科学论文上的多模态多文档 agentic deep research 基准。
- 通用 RAG/搜索 Agent 基准：**CRAG benchmark**（Yang et al., NeurIPS 2024，4,409 题，Meta KDD Cup 2024）、**BrowseComp**（OpenAI，arXiv 2504.12516，2025）、**SimpleQA**（arXiv 2411.04368）与 **Chinese SimpleQA**（ACL 2025）。
- 意义：中期报告表 3-5 中"接入真实数据源后评测""构建评测集后量化"两个空格，**可以直接采用 LitSearch/SAGE 的查询构造与判定协议**，不必从零发明。

### 1.4 引用可信与自动核验：本课题最值得深挖的研究富矿

- **ALCE**（Gao, Yen, Yu et al., EMNLP 2023，218 引用）：带引用生成的自动评测事实标准，指标为 **citation recall/precision + NLI entailment**，与本系统 D7（预编号引用）/D8（两级核验）完全同构。**中期报告未引用，建议必补。**
- **MiniCheck**（Tang, Laban, Durrett; EMNLP 2024，54 引用）：400M 参数小模型达到 GPT-4 级 grounding 事实核查准确率、成本极低——是 Stage 7 **L2 语义核验（当前为 pass-through）的现成落地方案**，可经统一 OpenAI 兼容客户端（D1）调用，亦可本地部署。
- Liu, Zhang, Liang：*Evaluating Verifiability in Generative Search Engines*（Findings of EMNLP 2023，143 引用）：人审 Perplexity/Bing Chat 等，发现引用召回率（statement 被引用覆盖的比例）普遍偏低。是"生成不可信"动机章节有力量化证据。
- 配套方法：
  - **AlignScore**（Zha et al., ACL 2023，81 引用）：统一对齐函数评事实一致性；
  - **RARR**（Gao et al., arXiv 2210.08726）：用检索+后编辑把归因"修回去"；
  - **FACTS Grounding 排行榜**（Google，arXiv 2501.03200，2025）：长文（≤32k token 文档）完全 grounded 评测；
  - 命题级粒度研究：Gunjal & Durrett（Findings of EMNLP 2024）讨论 atomic proposition 的上下文必要性；
  - **InFi-Check**（EMNLP 2026）：细粒度错误类型的可解释事实核查；
  - **Verbal-R3**（ACL 2026）：用"语言化注释"桥接检索结果与 LLM 推理。
- 与 **D9（抽取式证据、逐字匹配）**直接呼应：
  - *Guaranteeing Faithful Evidence Extraction in Speculative RAG*（arXiv 2609.10046，2026）专门讨论如何保证引用/抽取片段**逐字来自被检索文档**，正是 D9 的形式化论证来源；
  - **EXIT**（Findings of ACL 2025，10 引用）证明抽取式上下文压缩比抽象式更忠实；
  - **RECOMP**（Xu et al., arXiv 2310.04408）：检索后压缩与选择性增强，降本同时减少噪声。

### 1.5 重排前沿（报告引用的 RankRAG/RankCoT/ListT5 均已核实，缺后续脉络）

- **RankGPT**（Sun et al., EMNLP 2023，281 引用）：LLM 作为重排 Agent 的滑动窗口 listwise 方法，是这一支的源头。
- **RankRAG**（Yu et al., NeurIPS 2024，48 引用）✓、**RankCoT**（Wu et al., ACL 2025 long，9 引用；arXiv 2502.17888）✓、**ListT5**（Yoon et al., ACL 2024，14 引用）✓。
- **Rank1**（Weller et al., arXiv 2502.18418，2025）：首个利用 test-time compute 的重排模型，用 R1 式推理轨迹（60 万+样本）蒸馏小模型。
- WWW 2025 工程改进：**PE-Rank**（用 passage embedding 降低 listwise 成本，DOI 10.1145/3696410.3714554）、**自校准 listwise**（DOI 10.1145/3696410.3714658）；*DynamicRAG*（NeurIPS 2025）把 LLM 输出作为重排反馈。
- 实用结论（证据比写报告时更强）：**cross-encoder 粗排 + LLM listwise 精排（仅 top-N）** 是主流两级形态；多样性用 MMR；权威性可直接用 OpenAlex `cited_by_count` 做领域/年份归一化。

### 1.6 查询理解与改写

- **UniRAG**（Kim et al., Findings of EMNLP 2025，DOI 10.18653/v1/2025.findings-emnlp.1022）：统一框架做查询分解（decomposition）、break-down 推理与迭代改写。⚠️ **注意：其内容侧重分解/推理/改写，并非"抽取主体-约束-意图字段"，中期报告 2.2 的表述需回原文核对（见 §5）。**
- **HyDE**（Gao et al., ACL 2023，363 引用）：先让 LLM 零样本生成"假设性文档"再做稠密检索，无标注场景下显著提效——稠密召回腿的低成本增强。
- **Step-Back Prompting**（Zheng et al., arXiv 2310.06117，2023）：先抽象出高层概念再检索/推理。
- **MaFeRw**（AAAI 2025，DOI 10.1609/aaai.v39i24.34732）：多方面反馈的查询改写。
- **Clarify-Then-Search**（KDD 2026，DOI 10.1145/3770855.3817986）：欠规约查询先澄清约束再深度检索，指出缺约束会导致检索漂移——支持"先反问再检索"的交互设计。

### 1.7 自动评测

- **RAGAS**（Es et al., EACL 2024 demo，668 引用）：无参考答案的忠实性/答案相关性/上下文相关性自动评测（报告已引 ✓）。
- **ARES**（Saad-Falcon et al., NAACL 2024，149 引用）：合成数据训练轻量评判器并给置信区间（报告已引 ✓）。
- **RAGChecker**（Ru et al., NeurIPS 2024，38 引用）：把输出拆成 claim、分别诊断检索与生成两端的细粒度指标——**比 RAGAS 更适合放进本系统的评测闭环**。
- **RAG-Critic**（Dong et al., ACL 2025，10 引用）：批评者模型做 on-policy 评估与错误导向纠错（报告已引 ✓）。
- **eRAG**（Salemi & Zamani, SIGIR 2024，169 引用）：警告仅按相关性标签评检索，与 RAG 下游生成质量相关性有限——**检索指标与生成指标必须同时报**。
- 长文/综述评测：**Bloom-Eval**（ACL 2026，基于 Bloom 分类法六级评测自动综述生成）、**TaxoAlign**（EMNLP 2025，评测综述结构/分类法）、**ResearchRubrics**（arXiv 2511.07685，2025）、**DEER**（arXiv 2512.17776，2025）。

### 1.8 成本、缓存与压缩

- **FrugalGPT**（Chen, Zaharia, Zou; arXiv 2305.05176，2023，62 引用）：提示压缩 + 模型级联 + 缓存三件套。
- 语义缓存：GPTCache 生态的实证研究 *GPT Semantic Cache*（arXiv 2411.05276）、**MeanCache**（IPDPS 2025，DOI 10.1109/ipdps64566.2025.00117）。
- **CacheBlend**（arXiv 2405.16444，2024；当日 arXiv 页面核实）：RAG 场景跨请求 KV cache 融合复用（需自托管推理栈，属远期）。
- 上下文压缩：**xRAG**（Cheng et al., NeurIPS 2024，27 引用，报告已引 ✓）、**LongLLMLingua**（Jiang et al., ACL 2024，106 引用）、RECOMP、EXIT。

### 1.9 知识图谱与引文图

- **GraphRAG**（Edge et al., arXiv 2404.16130，2024，160 引用）：社区摘要回答"整个语料库的主题是什么"类全局问题。
- **LightRAG**（Guo et al., Findings of EMNLP 2025，209 引用）：图结构上的低成本增量 RAG。
- **Graphusion**（WWW 2025，DOI 10.1145/3701716.3717821）：科学知识图谱构建。
- **CO-Search**（2024，语义检索 + 引文图联合检索的文献综述助手；⚠️ 本次未在 OpenAlex 定位到记录，正式引用前需回源核对）：方法学上支持报告已承诺但未实现的"引文扩展"。

---

## 2. 现状 vs 前沿：差距对照（基于 2026-11-02 工作树）

| 阶段 | 代码真实现状 | 前沿对照与差距 |
|---|---|---|
| Stage 1 查询解析 | 关键词抽取 + 规则意图分类的 stub（`stage1_query.py`） | QueryContract 的 LLM 解析/校验重试/降级仅存在于设计；无分解、HyDE、复杂度路由 |
| Stage 2 召回 | **返回 mock 假论文**，无任何真实外部 API（`stage2_recall.py`） | OpenAlex 当日实测可直连（无 key，含引用量/年份/摘要/引文关系）；多路+引文扩展全缺 |
| Stage 3 融合 | RRF 跑在 mock 列表上，仅按 id 去重 | DOI/标题归一化去重、可学习权重、相关性反馈未实现 |
| Stage 4 重排 | 分数求和的 stub（`stage4_rerank.py`） | BGE cross-encoder、按意图加权、MMR、LLM listwise 全缺 |
| Stage 5 证据 | **mock 句子**，无逐字保证（`stage5_evidence.py`） | D9 要求 verbatim；EXIT、arXiv 2609.10046 提供方法学依据 |
| Stage 6 综述 | 模板话术，输出中带 "skeleton/demo" 声明 | STORM/AutoSurvey 的大纲驱动生成未实现 |
| Stage 7 核验 | L1 已接线，**L2 是文档化的 pass-through**（`stage7_verify.py`） | MiniCheck/ALCE 指标可直接替换；命题切分与 entailment 未做 |
| Stage 8 导出 | Markdown/BibTeX/JSON 已实现（123 行） | 基本完成；多轮引用一致性可补 |
| Agent | `graphs/agent.py`（337 行）+ 四护栏（步数/Token/循环/连续错误）已实现 | 护栏是亮点；但尚无"低置信→补检索"的条件边（CRAG 回路） |
| 评测 | **无评测集、无指标闭环**；表 3-5 指标全部"待评测" | LitSearch/SAGE 协议 + RAGChecker/ALCE/eRAG 指标可直接采用 |
| 成本观测 | Token 预算实时跟踪 + trace 已有 | Adaptive-RAG 路由、语义缓存、prompt caching 未启用，缺真实成本数据 |

---

## 3. 优化方向（三层）

### Tier 1：答辩前把"设计"变成"实现 + 数字"（最高杠杆）

1. **接通真实召回，OpenAlex 优先**。当日实测：免费、无 key、本机可直连；标题/摘要/年份/venue/引用量/参考文献与被引关系齐全，一个源同时喂饱权威、时效、引文扩展三个特征。arXiv 主站、Semantic Scholar（需退避限流，当日返回 429）作为第二、三路。mock 保留为测试 fixture（沿用 `tests/conftest.py` 的 fake 体系，离线单测不依赖网络）。
2. **L2 语义核验落地为 NLI/MiniCheck 式 entailment**：命题切分 → 逐命题判定 → 输出每句"支撑/不支撑"。配套 **ALCE 的 citation precision/recall**，使表 3-5 的"引用准确率/证据支撑率"出数。
3. **评测闭环（最能体现可验证性）**：按 LitSearch/SAGE 的构造方式建 50–100 条本领域金标查询；指标覆盖契约解析成功率、Recall@K/MRR、citation P/R、RAGChecker 式 claim 忠实度、token/P95/失败率；一条命令产出回归报告。同时满足 TDD 与报告真实性要求。
4. **真实 QueryContract LLM 解析 + 降级**：把已完成的设计接线（Pydantic 校验、一次重试、关键词降级），并挂"解析成功率"指标；稠密召回腿加 **HyDE**（一个 prompt 的成本）。
5. **两级重排**：本地 BGE cross-encoder 粗排 → top-20 LLM listwise 精排（按意图触发，控成本）；MMR 保多样性；权威分按领域/年份归一化。
6. **证据逐字落库（D9 工程化）**：写入 EvidenceChunk 时存原文片段 + 字符 offset，落库前强制字符串匹配，而不是事后检查。
7. **成本三件套出真实数据**：规则版复杂度路由（Adaptive-RAG-lite）跳过不必要检索 + 高频子查询语义缓存 + 供应商 prompt caching；用实测数据对标 ≤10K tokens、P95 ≤3s、E2E ≤60s。

### Tier 2：理论深度与答辩亮点（设计 + 小规模实现）

8. **CRAG 式纠正回路（把 LangGraph 用在刀刃上）**：融合后加检索置信评估器，低置信→分解重写→补检索一次；综述后低支撑命题同样触发一次有界补检索。回路步数受现有四护栏约束——这是 D2"确定性流水线优先、有界 Agent"的最佳实证，也回答了"为什么要迁移 LangGraph"（条件边）。
9. **大纲驱动综述（STORM/AutoSurvey-lite）**：证据先聚类成大纲，再逐节生成、逐句挂预编号引用；结构质量用 TaxoAlign/Bloom-Eval 的简化思路打分。
10. **引文图扩展一跳**：用 OpenAlex `referenced_works`/`cited_by_api_url` 实现报告已承诺的引文扩展，替代当前缺失环节。
11. **澄清式交互（可选，演示效果好）**：欠规约复杂查询先反问一个约束问题（Clarify-Then-Search），前端现有 SSE 通道天然支持。
12. **PaperQA2 式小型人-机对比评测**：20–30 个任务上由作者/同学/导师盲评检索、综述与矛盾检测；成本极低但答辩可信度极高，可直接写成论文评测一章。

### Tier 3：写入"未来工作/相关工作"即可，不要现在建

RL 搜索 Agent（Search-R1/ReSearch/WebDancer/WebSailor）、GraphRAG 个人语料库、SAGE/AutoResearchBench/INSPIRE/CompLit 上的系统对比实验。用于"研究局限与展望"，展示对前沿边界的掌握。

---

## 4. 建议推进顺序

**真实数据（#1）→ 逐字证据（#6）→ L2 + ALCE（#2）→ 评测闭环（#3）→ 查询/重排（#4、#5）→ CRAG 回路（#8）→ 成本（#7）→ 综述升级（#9）。**

前三步构成最小可信闭环：**真实输入 → 可回溯证据 → 可量化的可信输出**；此后每一步都由评测集量化回归，符合 D1/D2/D7–D10 与 TDD 约定。每个方向单独发起设计评审，不在本调研内直接实现。

---

## 5. 对中期报告的两处修订提醒（报告真实性）

1. **UniRAG 引用需复核**。报告称"UniRAG（ACL 2025）对复杂查询先做统一结构化理解（抽取主体、约束与意图等字段）"。当日 OpenAlex 实测唯一相关记录为 *UniRAG: A Unified RAG Framework for Knowledge-Intensive Queries with Decomposition, Break-Down Reasoning, and Iterative Rewriting*（**Findings of EMNLP 2025**，DOI 10.18653/v1/2025.findings-emnlp.1022），venue 与内容描述均有出入。请回原文核对后再定稿，避免答辩被追问。
2. **建议补引**：§2.4 补 ALCE（EMNLP 2023）与 MiniCheck（EMNLP 2024）；§2.6 工业界/学术系统补 PaperQA、PaperQA2、STORM、AutoSurvey；评测一节补 RAGChecker（NeurIPS 2024）、eRAG（SIGIR 2024）；第五章展望补 SAGE、AutoResearchBench、INSPIRE、CompLit（均 2026）。

---

## 附录：文献核实表（2026-11-02）

> 引用量为 OpenAlex 当日快照。✅ = 当日实测；⚠️ = 未独立核实，正式定稿前回源。

| # | 文献 | 年份 / venue | DOI / arXiv | 引用量 | 状态 |
|---|---|---|---|---|---|
| 1 | RAG: Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al.) | NeurIPS 2020 | — | — | 报告已引，未当日复核 |
| 2 | ReAct: Synergizing Reasoning and Acting (Yao et al.) | ICLR 2023 | — | — | 报告已引，未当日复核 |
| 3 | UniRAG: Unified RAG with Decomposition, Break-Down Reasoning, Iterative Rewriting (Kim et al.) | Findings of EMNLP 2025 | 10.18653/v1/2025.findings-emnlp.1022 | 0 | ✅ |
| 4 | LitSearch: A Retrieval Benchmark for Scientific Literature Search (Ajith et al.) | EMNLP 2024 | 10.18653/v1/2024.emnlp-main.840 | 13 | ✅ |
| 5 | Reciprocal Rank Fusion（RRF, Cormack et al.） | SIGIR 2009 | — | — | 报告已引，未当日复核 |
| 6 | RankRAG: Unifying Context Ranking with RAG (Yu et al.) | NeurIPS 2024 | 10.52202/079017-3850 | 48 | ✅ |
| 7 | RankCoT: Refining Knowledge for RAG through Ranking CoT (Wu et al.) | ACL 2025 | 10.18653/v1/2025.acl-long.629；arXiv 2502.17888 | 9 | ✅ |
| 8 | ListT5: Listwise Reranking with FiD (Yoon et al.) | ACL 2024 | 10.18653/v1/2024.acl-long.125 | 14 | ✅ |
| 9 | RankGPT: Is ChatGPT Good at Search? (Sun et al.) | EMNLP 2023 | 10.18653/v1/2023.emnlp-main.923 | 281 | ✅ |
| 10 | Rank1: Test-Time Compute for Reranking in IR (Weller et al.) | 2025 预印本 | arXiv 2502.18418 | 1 | ✅ |
| 11 | PE-Rank: Passage Embeddings for Efficient Listwise Reranking | WWW 2025 | 10.1145/3696410.3714554 | 16 | ✅ |
| 12 | Self-Calibrated Listwise Reranking with LLMs | WWW 2025 | 10.1145/3696410.3714658 | 9 | ✅ |
| 13 | DynamicRAG: LLM Outputs as Feedback for Dynamic Reranking | NeurIPS 2025 | 10.52202/085713-5620 | 3 | ✅ |
| 14 | Verbal-R3: Verbal Reranker between Retrieval and Reasoning | ACL 2026 | 10.18653/v1/2026.acl-long.1712 | 0 | ✅ |
| 15 | BGE 系列（GTE: Improving Text Embeddings with LLMs, Wang et al.） | ACL 2024 | 10.18653/v1/2024.acl-long.642 | 150 | ✅ |
| 16 | Self-RAG: Learning to Retrieve, Generate, Critique (Asai et al.) | ICLR 2024 | arXiv 2310.11511 | 101（OpenAlex） | ✅ |
| 17 | RAGTruth: A Hallucination Corpus (Niu et al.) | ACL 2024 | 10.18653/v1/2024.acl-long.585 | 119 | ✅ |
| 18 | xRAG: Extreme Context Compression with One Token (Cheng et al.) | NeurIPS 2024 | 10.52202/079017-3476 | 27 | ✅ |
| 19 | Adaptive-RAG (Jeong et al.) | NAACL 2024 | 10.18653/v1/2024.naacl-long.389 | 259 | ✅ |
| 20 | Corrective RAG / CRAG (Yan et al.) | 2024（SSRN/arXiv） | 10.2139/ssrn.5267341 | 182 | ✅（arXiv 编号未当日复核） |
| 21 | Active RAG / FLARE (Jiang et al.) | EMNLP 2023 | 10.18653/v1/2023.emnlp-main.495 | 499 | ✅ |
| 22 | IRCoT (Trivedi et al.) | ACL 2023 | 10.18653/v1/2023.acl-long.557 | 352 | ✅ |
| 23 | Agentic RAG: A Survey (Singh et al.) | 2025 预印本 | arXiv 2501.09136 | 37 | ✅ |
| 24 | Data-Centric Perspectives on Agentic RAG: A Survey | Findings of ACL 2026 | 10.18653/v1/2026.findings-acl.78 | 1 | ✅ |
| 25 | Reflective RAG: Self-Evaluation Driven Strategy Optimization | Findings of ACL 2026 | 10.18653/v1/2026.findings-acl.648 | 1 | ✅ |
| 26 | PaperQA: Retrieval-Augmented Generative Agent for Scientific Research | 2023 预印本 | arXiv 2312.07559 | — | ✅ arXiv |
| 27 | PaperQA2: Language Agents Achieve Superhuman Synthesis of Scientific Knowledge (Skarlinski et al.) | 2024 预印本 | arXiv 2409.13740 | 49 | ✅ |
| 28 | ResearchAgent: Iterative Research Idea Generation (Baek et al.) | NAACL 2025 | 10.18653/v1/2025.naacl-long.342 | 46 | ✅ |
| 29 | STORM: Writing Wikipedia-like Articles From Scratch (Shao et al.) | NAACL 2024 | 10.18653/v1/2024.naacl-long.347 | 41 | ✅ |
| 30 | AutoSurvey: LLMs Can Automatically Write Surveys (Wang et al.) | NeurIPS 2024 | 10.52202/079017-3655 | 25 | ✅ |
| 31 | SurveyG: Multi-Agent Framework with Hierarchical Citation Graph | 2025 预印本 | arXiv 2510.07733 | 0 | ✅ |
| 32 | SurveyForge / SurveyX | 2025 | — | — | ⚠️ 未独立核实 |
| 33 | DancerSurvey: End-to-End Deep Research Agent for Survey Generation | 2025 预印本 | — | — | ⚠️ 未独立核实 |
| 34 | Feedback Is The Key for Automated Survey Generation | Findings of ACL 2026 | 10.18653/v1/2026.findings-acl.1904 | 0 | ✅ |
| 35 | Bloom-Eval: Hierarchical Benchmark for Automatic Survey Generation | ACL 2026 | 10.18653/v1/2026.acl-long.1315 | 0 | ✅ |
| 36 | TaxoAlign: Scholarly Taxonomy Generation Using LLMs | EMNLP 2025 | 10.18653/v1/2025.emnlp-main.1536 | 2 | ✅ |
| 37 | Aviary: Training Language Agents on Challenging Scientific Tasks | 2024 预印本 | arXiv 2412.21154 | 10 | ✅ |
| 38 | ALCE: Enabling LLMs to Generate Text with Citations (Gao et al.) | EMNLP 2023 | 10.18653/v1/2023.emnlp-main.398 | 218 | ✅ |
| 39 | MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents (Tang et al.) | EMNLP 2024 | 10.18653/v1/2024.emnlp-main.499 | 54 | ✅ |
| 40 | Evaluating Verifiability in Generative Search Engines (Liu, Zhang, Liang) | Findings of EMNLP 2023 | 10.18653/v1/2023.findings-emnlp.467 | 143 | ✅ |
| 41 | AlignScore: Unified Alignment Function (Zha et al.) | ACL 2023 | 10.18653/v1/2023.acl-long.634 | 81 | ✅ |
| 42 | RARR: Researching and Revising What LLMs Say (Gao et al.) | 2022 预印本 | arXiv 2210.08726 | — | ✅ arXiv |
| 43 | FACTS Grounding Leaderboard (Jacovi et al.) | 2025 预印本 | arXiv 2501.03200 | 2 | ✅ |
| 44 | InFi-Check: Interpretable Fine-Grained Fact-Checking | EMNLP 2026 | 10.18653/2026.emnlp-main.1136 | 0 | ✅ |
| 45 | Guaranteeing Faithful Evidence Extraction in Speculative RAG (Signé et al.) | 2026 预印本 | arXiv 2609.10046 | 0 | ✅ |
| 46 | EXIT: Context-Aware Extractive Compression for RAG (Hwang et al.) | Findings of ACL 2025 | 10.18653/v1/2025.findings-acl.253 | 10 | ✅ |
| 47 | RECOMP: Compression and Selective Augmentation (Xu et al.) | 2023 预印本 | arXiv 2310.04408 | 16 | ✅ |
| 48 | LongLLMLingua (Jiang et al.) | ACL 2024 | 10.18653/v1/2024.acl-long.91 | 106 | ✅ |
| 49 | RAGAS (Es et al.) | EACL 2024 demo | 10.18653/v1/2024.eacl-demo.16 | 668 | ✅ |
| 50 | ARES (Saad-Falcon et al.) | NAACL 2024 | 10.18653/v1/2024.naacl-long.20 | 149 | ✅ |
| 51 | RAGChecker (Ru et al.) | NeurIPS 2024 | 10.52202/079017-0692 | 38 | ✅ |
| 52 | RAG-Critic (Dong et al.) | ACL 2025 | 10.18653/v1/2025.acl-long.179 | 10 | ✅ |
| 53 | eRAG: Evaluating Retrieval Quality in RAG (Salemi & Zamani) | SIGIR 2024 | 10.1145/3626772.3657957 | 169 | ✅ |
| 54 | CRAG — Comprehensive RAG Benchmark (Yang et al.) | NeurIPS 2024 | 10.52202/079017-0335 | 41 | ✅ |
| 55 | BrowseComp (Wei et al.) | 2025 预印本 | arXiv 2504.12516 | 2 | ✅ |
| 56 | SimpleQA (Wei et al.) | 2024 预印本 | arXiv 2411.04368 | 14 | ✅ |
| 57 | Chinese SimpleQA | ACL 2025 | 10.18653/v1/2025.acl-long.941 | 9 | ✅ |
| 58 | SAGE: Benchmarking and Improving Retrieval for Deep Research Agents (Hu et al.) | 2026 预印本 | arXiv 2602.05975 | 0 | ✅ |
| 59 | AutoResearchBench (Xiong et al.) | 2026 预印本 | arXiv 2604.25256 | 1 | ✅ |
| 60 | INSPIRE: Scientific Literature Search for Open Research Problems (Ding et al.) | 2026 预印本 | arXiv 2609.33233 | 0 | ✅ |
| 61 | CompLit: Implicit, Cumulative, and Unmet Needs in Literature Search (Ko et al.) | 2026 | 无 DOI 记录 | 0 | ✅（题名/年份） |
| 62 | PaperScope: Multi-Modal Multi-Document Benchmark for Agentic Deep Research | 2026 预印本 | arXiv 2604.11307 | 0 | ✅ arXiv |
| 63 | ResearchRubrics: Evaluating Deep Research Agents | 2025 预印本 | arXiv 2511.07685 | 1 | ✅ |
| 64 | DEER: Benchmark for Deep Research Expert Report Generation | 2025 预印本 | arXiv 2512.17776 | 1 | ✅ |
| 65 | HyDE: Precise Zero-Shot Dense Retrieval (Gao et al.) | ACL 2023 | 10.18653/v1/2023.acl-long.99 | 363 | ✅ |
| 66 | Take a Step Back: Evoking Reasoning via Abstraction (Zheng et al.) | 2023 预印本 | arXiv 2310.06117 | 27 | ✅ |
| 67 | MaFeRw: Query Rewriting with Multi-Aspect Feedbacks | AAAI 2025 | 10.1609/aaai.v39i24.34732 | 16 | ✅ |
| 68 | Clarify-Then-Search | KDD 2026 | 10.1145/3770855.3817986 | 0 | ✅ |
| 69 | Search-R1 (Jin et al.) | 2025 预印本 | arXiv 2503.09516 | 13 | ✅ |
| 70 | ReSearch: Learning to Reason with Search (Chen et al.) | NeurIPS 2025 | 10.52202/085713-2858 | 12 | ✅ |
| 71 | R1-Searcher++: Dynamic Knowledge Acquisition via RL | 2025 预印本 | arXiv 2505.17005 | 2 | ✅ |
| 72 | WebDancer: Towards Autonomous Information Seeking Agency (Wu et al.) | NeurIPS 2025 | 10.52202/085713-4035 | 4 | ✅ |
| 73 | WebSailor: Training Superhuman Open Web Search Agents | 2025 | — | — | ⚠️ 未独立核实 |
| 74 | DeepResearcher: Scaling Deep Context-Processing with Agentic Workflow | 2025 | — | — | ⚠️ 未独立核实 |
| 75 | T-Search: Open Agentic Retriever for Hard Multi-Step Search | 2026 预印本 | arXiv 2610.06782 | 0 | ✅ |
| 76 | FrugalGPT (Chen, Zaharia, Zou) | 2023 预印本 | arXiv 2305.05176 | 62 | ✅ |
| 77 | GPT Semantic Cache (Regmi et al.) | 2024 预印本 | arXiv 2411.05276 | 1 | ✅ |
| 78 | MeanCache: User-Centric Semantic Caching | IPDPS 2025 | 10.1109/ipdps64566.2025.00117 | 19 | ✅ |
| 79 | CacheBlend: Fast LLM Serving for RAG with Cached Knowledge Fusion | 2024 预印本 | arXiv 2405.16444 | — | ✅ arXiv |
| 80 | GraphRAG: From Local to Global (Edge et al.) | 2024 预印本 | arXiv 2404.16130 | 160 | ✅ |
| 81 | LightRAG (Guo et al.) | Findings of EMNLP 2025 | 10.18653/v1/2025.findings-emnlp.568 | 209 | ✅ |
| 82 | Graphusion: RAG for Scientific KG Construction | WWW 2025 | 10.1145/3701716.3717821 | 25 | ✅ |
| 83 | CO-Search: Literature Review with Semantic + Citation Graph Search | 2024 | — | — | ⚠️ 未独立核实 |
| 84 | CiteBench: Benchmark for Scientific Citation Text Generation (Funkquist et al.) | EMNLP 2023 | 10.18653/v1/2023.emnlp-main.455 | 4 | ✅ |
| 85 | IdeaBench: Benchmarking LLMs for Research Idea Generation | KDD 2025 | 10.1145/3711896.3737419 | 9 | ✅ |
