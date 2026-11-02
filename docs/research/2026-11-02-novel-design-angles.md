# 2026 前沿补充调研：差异化设计方向（Novel Design Angles）

- **调研日期**：2026-11-02
- **调研人**：刘昆（与 AI 协作完成）
- **定位**：本文是 [`2026-11-02-frontier-optimization.md`](./2026-11-02-frontier-optimization.md)（下称"一份报告"，含 85 条文献基线）的**严格增量**。一份报告给的是"把设计补齐"的标准动作（OpenAlex 真实召回、MiniCheck 式 L2、CRAG 回路、STORM 式综述、评测闭环……）；本文只回答一个问题：**怎样设计，才能在答辩与论文中体现"我对现有方案做过独立审视与升级"，而不是把 2024–2025 的主流方案重述一遍。**
- **代码基线**：分支 `langgraph-inte`（工作树，2026-11-02）。本文是调研产物（spike），不构成实现设计；任何方向落地前另走设计评审 + TDD。

## 0. 方法、范围与可信度声明

- 检索以 **2026 年发表**为主（少量 2025 末期刊在线版），来源为 OpenAlex（`from_publication_date:2026-01-01`，经 curl 直连）、Crossref 连通性测试；dblp 当日不可达（HTTP 000），OpenReview 403，arXiv 主站限流。
- 每个核心锚点均拉取了 OpenAlex 全记录（作者、摘要、venue）核对内容，而非只看题名。✅ = 题名/日期/venue/DOI 经 OpenAlex 实测，其中标注"摘要已核"的 additionally 核对了摘要主张；⚠️ = 仅列表级元数据一致、未读全文，正式写入论文前回源。
- **额度限制如实披露**：OpenAlex 匿名共享额度在第二批查询中段耗尽，14 个补充查询（持续式 RAG、命题索引、弃权等）未完成；这些簇的结论由**已核实**文献支撑，但"不存在反例"不做保证。
- 2026 年新预印本引用量为 0–个位数是正常时滞，不代表质量；本文不以引用量论高下。
- 一条被记忆"猜"出的 OpenScholar arXiv 编号经 arXiv 页面实测为**无关论文**，故本文只引其 Nature DOI，不给 arXiv 编号。

---

## 1. 2026 年的形势：四个已经移动的坐标系

理解差异化主张前，先记录 2026 年相对一份报告基线发生的四个变化：

1. **科研综合系统已登上 Nature 正刊，且评测对象变成"深度研究"本身。**
   - **OpenScholar**（Asai, He, Shao, Shi et al., *Nature*, 2026-02，DOI 10.1038/s41586-025-10072-4，摘要已核，当日 38 引）：检索 4,500 万篇开放获取论文、带引用综合回答的 8B 开源专用模型；配套 **ScholarQABench**（2,967 条专家查询、208 份长答案，覆盖 CS/物理/神经/生物医学）。它比 PaperQA2 更适合做正面对位系统。
   - **Co-Scientist**（Gottweis, Weng, Tu et al., *Nature*, 2026-05，DOI 10.1038/s41586-026-10644-y，当日 160 引）：Gemini 多智能体，用 test-time compute 做"生成—批判—精炼"的锦标赛式**假设发现**。
   - 深度研究评测/系统在 2026 年密集出现：IDRBench（交互式）、MiroEval（过程+结果双评）、MMDeepResearch-Bench（多模态）、Ko-WideSearch（广度穷举）、LitReview Arena（专家对战评审）、MiroFlow/O-Researcher/IntentRL（开源/RL 系统）。
2. **研究问题从"怎么接检索"变成"何时检索、检索了是否被使用"。** 针对 R1/o1 类长思维链推理模型，2026 年出现步级检索时机（ReaLM-Retrieve）、"自适应检索的收益主要来自不检索"的反直觉证据、以及"证据脱离"（evidence disengagement：证据摆在上下文里模型也不看）现象。
3. **"核验器"本身成为被审计对象。** 2026 年有工作直接测量 OpenScholar 与 PaperQA2 的引用核验器：同一批输出，仅因核验器宽严不同，未支撑引用率从 ~3% 摆到 ~18%，阴性一致率仅 0.27–0.30——跨论文横向比较因此失效。
4. **"覆盖全不全"与"会不会拒答"成为一等指标。** 广度穷举检索、集合级打分、命题级 conformal 风险保证、证据门控，都是 2026 年的新焦点；与此同时，**跨会话智能体记忆被正式形式化为推荐问题**，为本系统名称中的"推荐"二字提供了 2026 年的理论入口。

下面 7 条设计主张（M1–M7）都建立在这四个移动之上。每条按同一结构写：**现有主流方案 → 2026 证据 → 我的升级主张 → 与 D1/D2/D7–D10 的关系 → 最小实现切片（答辩前）→ 度量 → 诚实标注**。

---

## 2. 七条差异化设计主张

### M1 构造即合法：引用语法约束 + 证据 span 复制约束（D7/D9 从"提示+事后检查"升级为"输出契约"）

**主流做法**：提示词要求"只能引用 [1..N]"，生成后再跑核验；PaperQA2/OpenScholar 用一个固定的 attribution model 做事后判定。

**2026 证据**：
- **FullCite**（Yeginbergen, Wührl, Rogers, Agerri; arXiv 2606.07130，摘要已核）：每条 claim 结构化地同时链接到**来源文档与支撑证据 span**；比较三条技术路线——提示生成、**在引用文法上做受限解码（constrained decoding over a citation grammar）**、事后 span 对齐。
- **When Copying Is Hard**（arXiv 2610.28393，摘要已核）：构造基准测试"逐字复现上下文片段"能力，发现即使目标串就在上下文里，模型仍频繁漂移/停不准边界；给出 copy-constrained decoding 方案。
- **ATTRICITE**（arXiv 2609.14248，摘要已核）：开源 4B **引用恢复**模型（给定含引用的段落，恢复原作者引用的是哪篇论文）+ CITEALIGN（7,607 例近期 CS 文献数据集）+ CiteGuard 检索环境——把"引用是否指向正确来源"变成可测的独立能力。
- Guaranteeing Knowledge Integration with Joint Decoding（arXiv 2604.08046）：联合解码强制使用检索知识。

**升级主张**：把 D7/D9 的执行点**从 Stage 7 提前到生成契约本身**。综述不再是自由文本，而是 claim 序列的结构化文档：
`claims: [{text, citation_ids⊆当前证据编号集, span_id, start, end}]`。
- citation_id 的合法值域就是当前证据编号集——**非法编号在语法层不可能出现**（D7 由构造保证，而非靠提示）；
- span 只能"复制"源文本且字符 offset 必须匹配（D9 由构造+落库双重保证）；
- 校验失败由 LangGraph 节点拒绝并触发**一次**有界修复（受 D2 四护栏约束）。

**与不变量的关系**：D7、D9 的执行机制升级；不引入新客户端（D1）；修复回路有界（D2）；全部结构挂在 D10 同一上下文。

**最小切片（答辩前，免训练、确定性）**：
1. TDD：先写测试——非法 citation_id 必被拒、offset 不匹配必被拒、修复后二次失败则该 claim 降级为无引用断言；
2. Stage 6 改为结构化 schema 生成（Pydantic 校验，沿用 D1 客户端的 JSON/结构化输出能力）；新增一个纯函数校验节点；
3. 商业端点不暴露 logits，"受限解码"落地为**结构化生成 + 确定性投影/拒绝修复**——论文中必须如实写成"契约级约束"，不得声称解码级保证（这也是 FullCite 三路线之一，有文献依据）。

**度量**：非法引用率（目标构造为 0）、span verbatim 通过率、首次生成合格率、修复触发率/修复成功率、ALCE citation P/R。

**为什么这是"升级"而不是"跟随"**：一份报告的 #2/#6 是"把 MiniCheck 接上、落库前字符串匹配"——仍是**事后审计**；M1 把不合法输出移到**不可能发生或不可流出系统**的位置，并能用消融（自由生成 vs 契约生成）证明审计压力下降。

---

### M2 带统计风险保证的选择性回答：命题级 conformal 门控 + 显式弃权优先

**主流做法**：核验输出二元 pass/fail；分数阈值靠经验；要么答要么不答，没有"风险-覆盖"可调旋钮。

**2026 证据**：
- **Conformal Factuality Control for Multi-Hop RAG**（arXiv 2609.38222，摘要已核）：把 **split-conformal claim filtering** 引入多跳 RAG，在六个模型×数据集配置上给出随风险水平变化的事实性保证。
- **Word-Level Conformal Risk Control under Domain Shift**（DOI 10.61424/ka6yps02，摘要已核）：在 RAGTruth 全语料（2,965 个证据源、17,790 条响应）上做词级幻觉检测，按来源划分防止泄漏，含确定性证据重叠规则等轻量检测器。
- **AB-RAG**（arXiv 2606.29090，摘要已核）：**免训练**，按问题难度自适应决定检索几篇，并给出"答案何时可信"的信号——正中本项目"不训练模型"的约束。
- Facet-Level Tracing of Evidence Uncertainty（arXiv 2604.09174）；Factual Confidence Prediction（arXiv 2605.05244）；UR-RAG 统一风险校准（Research Square 预印本）；RAGScope 成本感知证据门控（arXiv 2609.39075）。

**升级主张**：Stage 7 的输出从"通过/不通过"升级为**每命题风险分数 + 目标风险 α 下的选择性输出**：
- 命题切分 → entailment 打分 → 在小校准集上做 split-conformal 阈值；
- 不达标的命题三选一（按规则）：降级为"现有证据不足以断言……"的显式弃权、触发一次有界补检索（与 M4 共用介入点）、删除该命题；
- 对外暴露 α 旋钮：**同一系统可以在"高覆盖（敢说）/高保证（多说不知道）"之间给出风险-覆盖曲线**，而不是一个自夸的准确率。

**与不变量的关系**：D8（L2）的统计化；D2（补检索有界）；D1（打分经唯一客户端，或本地小模型）。

**最小切片（答辩前）**：50–100 条校准查询（与一份报告 #3 评测闭环共用）；确定性重叠规则 + 一个经 D1 的 NLI 打分；isotonic/conformal 阈值是纯函数（numpy 级，无新重依赖，如引入 scipy 需说明）；报告 risk–coverage 曲线、弃权率、弃权后错误率。

**为什么是升级**：当前 L2 是 pass-through，一份报告建议的是"接 MiniCheck"；M2 把"可信性"从一个**点估计指标**变成**带分布无关统计保证的可选行为**——这是答辩中可讲的方法论差异："系统不是更敢答，而是更知道什么时候不该答。"

---

### M3 核验者的核验：多验证器面板、证据升级与一致性披露

**动机证据（2026 年最有杀伤力的一条）**：
- **Evaluating and Guarding Citation Faithfulness in Agentic Scientific Synthesis**（arXiv 2607.20527，摘要已核）：直接审计 OpenScholar 与 PaperQA2——相同智能体输出上，测得未支撑引用率仅因核验器宽严不同就在 **~3% 到 ~18%** 之间；核验器对"哪些引用合格"高度一致、对"该标红哪些"却严重分歧（阴性一致率 0.27–0.30）。结论：没有任何单一标记集可信，跨论文横比无效。
- **DeepSciVerify**（arXiv 2605.27710，摘要已核）：摘要级初判 + 不确定时**升级**到全文 passage 的两段式验证；刻意利用不同模型"保守/果断"的互补性。
- HALLMARK（arXiv 2607.18360）：诊断 citation verifier 何时才该部署；Verified Misguidance（arXiv 2605.28565）：结构性引用失败分类；trajectory-judge（arXiv 2609.00038，摘要已核）：用配对判别（paired discrimination）暴露 judge 的虚报。

**升级主张**：L2 不押注任何单一判定器，而是一个**可审计面板**：
1. 确定性证据重叠规则（词级/命题级覆盖率，零成本）；
2. 两个**异构**判定（经 D1：不同 prompt 家族，如"包容式 NLI"与"对抗式找漏洞"，或不同模型）；
3. 分歧 → 升级到更细证据（摘要级 → span/全文级，复用 DeepSciVerify 的级联）；
4. 判定分歧、置信度、升级原因**全部进 trace 和导出报告**——核验结果不再是一个布尔值，而是"判决+合议庭意见"。

**最小切片**：三票 quorum（规则票 + 两 LLM 票）实现为 Stage 7 内纯函数；指标包含面板分歧率、升级率、各级严格度下的指标区间（直接复现 2607.20527 的"3%–18% 区间"报告形式，但报告在**自己系统**上）。M2 的 conformal 校准以面板聚合分数为输入。

**为什么是升级**：这是对"接一个 MiniCheck 就完事"的直接否定——2026 证据表明单验证器数字不可比；把**测量工具的不确定性**作为被测指标，是硕士论文中少见但极有说服力的自我审视。

---

### M4 检索时机：推理步级介入与"检索效用记账"（对 CRAG 的 2026 升级，而非 CRAG 复刻）

**与一份报告 #8（CRAG 回路）的区别先说清**：CRAG 问的是"这次检索质量好不好"；2026 年的问题是"**在推理的哪一步需要检索、检索回来的东西有没有真的被用到、哪些不检索反而更好**"。

**2026 证据**：
- **ReaLM-Retrieve / When to Retrieve During Reasoning**（arXiv 2604.26649，摘要已核）：面向 R1/o1 长思维链，三个机制——**推理步级**（非 token/句级）不确定性检测、学习式介入策略、推理中途证据注入。
- **Adaptive Retrieval helps Reasoning in LLMs — but mostly if it's not used**（arXiv 2602.07213，摘要已核）：智能体自主决定何时查知识库；反直觉结论是自适应的最大增益来自正确地**跳过**检索。
- **The Retrieval-Reasoning Paradox: Evidence Disengagement**（Zenodo 2026，DOI 10.5281/zenodo.19672442）：推理增强模型存在"证据脱离"。
- **R²-Searcher**（arXiv 2606.28566，摘要已核）：按 query token 语义（主体、动作、时间标记、程度修饰）抽取精确事实细粒度建模 + 检索后反思，显式校准"检索/推理边界"。
- Scaling RAR with Parallel Search and Explicit Merging（arXiv 2605.13534）；Ares: Adaptive Reasoning Effort Selection（arXiv 2603.07915）；LLM Agents Already Know When to Call Tools（arXiv 2605.09252）；A-RAG 分层检索接口（arXiv 2602.03442）。

**升级主张**：把**检索介入点**提升为显式架构对象，三处：查询前（Stage 2）、融合后（CRAG 质量门）、生成步级（知识缺口触发行）。每次介入产出一条**检索效用账**：
`决策{skip/retrieve/repair} → 触发原因 → 是否使用 → 使用后命题判决变化`，
四格统计：retrieved-used / retrieved-ignored（证据脱离的直接度量）/ retrieved-harmful / skipped-correct。策略保持**免训练规则**（缺口触发：数字、专名、比较主张、矛盾标记），全部受现有四护栏有界——与 Search-R1/IntentRL 等 RL 路线明确划界：**不训练、可复现、每一步可审计**，这恰好把 LangGraph 迁移的必要性落到"条件介入边"上（回答"为什么不是 if-else"）。

**最小切片（答辩前）**：Stage 6 两遍式——先出带缺口标记的草稿，对触发行开放**一次**步级补检索；trace 增加 utility 记录；在评测集上跑 always / never / adaptive 三臂消融，报 token、P95 与 citation P/R。

**为什么是升级**：一份报告的 CRAG 是"低置信→补检索"的单点回路；M4 给的是**时机理论 + 效用可观测性 + 反直觉假设（跳过检索可能更好）的消融验证**，叙事层次不同。

---

### M5 补齐"推荐"半壁：跨会话记忆即推荐 + 查询之外的可控新颖性

**动机（系统设计与系统名称的落差）**：系统名为"论文智能检索**与推荐**系统"，现设计只有检索-综合，没有任何推荐环节。这不是小缺口，而是**题目承诺未兑现**；2026 年的文献恰好把入口铺好了。

**2026 证据**：
- **Agent Memory as Recommendation**（arXiv 2610.34673，2026-10，摘要已核）：服务多会话的 LLM 智能体，每个请求都要从持续增长的记忆库、在有限上下文预算内选出少量记忆——作者论证这**就是推荐问题**（大库、每请求预算、多会话证据需齐备），并指出现有记忆系统几百上千次 LLM 调用却无人拆解哪部分真正有效。
- HARPO 层级 agentic 会话推荐（arXiv 2604.10048）；Information Fusion 2026 隐式愿望融合（DOI 10.1016/j.inffus.2026.104373）；Personalization and Evaluation of Conversational Information Access（arXiv 2606.13717）；TREC iKAT 2026 个性化会话检索 track（RALI@iKAT，arXiv 2610.17673）；Agentic Conversational Search with RL（arXiv 2601.13115）。
- 学术推荐侧 2026 仍在进展且强调**时序**：SPECTER-BS 引文推荐（*Knowledge and Information Systems*，DOI 10.1007/s10115-025-02677-y）、SciBERT+时序图注意力（JUCS，DOI 10.3897/jucs.176807）、TextTAGC 查询导向时序 GCN（*Scientometrics*，DOI 10.1007/s11192-025-05518-5）。
- **可控新颖性**：serendipity-control + 认知层级标签 + 解释的用户研究（*Scientific Reports*，2026-10，DOI 10.1038/s41598-026-78243-5）；Recommendation Systems for Exploratory Data Tasks（arXiv 2609.39412）。

**升级主张（两层）**：
1. **记忆即推荐**：把会话隐式事件（查询、展开某篇、导出 BibTeX、追问）沉淀为轻量研究兴趣画像；"下次检索/综述时让哪些历史论文与概念进入上下文"按推荐问题求解（预算内 top-m），与 M4 的介入点共用画像；
2. **查询之外的推荐**：每次回答后给一个小而多样的"你可能还没关注"集合——OpenAlex 引文图一跳（`referenced_works`/`cited_by_api_url`，一份报告 #10 的数据基础）∪ 画像近邻，经 MMR 去冗余、权威/新颖平衡，每条带"为什么推荐它"的一句话解释（经 D1）；提供新颖性档位（保守/探索），把 serendipity 的控制权显式交给用户。

**与不变量的关系**：推荐是流水线**尾部可选节点**（D2 默认路径不变）；解释同样受 D7/D9 约束（推荐理由只能引用真实元数据）；个人数据不出本机/私有库，呼应隐私约定。

**最小切片（答辩前）**：SQLite 事件表 + 确定性画像（概念词权、作者/venue 偏好，embedding 可选）；尾部 recommendation 节点输出 ≤5 条；评测用"会话后段 held-out 事件"做离线 P@5、 intra-list 多样性、新颖性（相对画像的距离），外加一份报告 #12 的小样本盲评。**RL 式主动意图（IntentRL）明确列入未来工作，不实现。**

**为什么是升级**：OpenScholar/PaperQA2/Co-Scientist 全部只回答被问的问题；"有记忆、会主动推荐、且新颖性可控"的可信论文助手，是本系统相对所有 2026 正面对位系统最清晰的产品级差异，且补上了题目自身的承诺。

---

### M6 覆盖度即一等目标：面向综述的集合检索 + 覆盖矩阵（把"没覆盖什么"做成输出）

**主流做法**：逐篇独立打分、分数求和取 top-N（本系统 Stage 3/4 正是如此）；综述质量只看最终文本。

**2026 证据**：
- **Ko-WideSearch**（arXiv 2606.27595，摘要已核）：web agent 评测几乎只考"深度"（链条尽头一个答案），**广度穷举**（列全一个闭集合并逐项填表属性）几乎无人评测；并指出"认证金标集合完整"远比"核对单答案"昂贵——综述写作面对的正是广度问题。
- **Scoring a Set, Not Summing Passage Scores**（arXiv 2607.05712）：集合级检索打分；CASI 集合干预信用分配（arXiv 2610.20293）。
- **EvidenceLens**（arXiv 2606.23724）：claim–evidence 矩阵的审计式呈现。
- LitReview Arena（arXiv 2608.21374，摘要已核）：~3k 专家判定、五个综述专用维度的盲评协议——"研究效用不只是参考文献重叠"。

**升级主张**：Stage 3/4 的选择对象从"单篇论文"改为"覆盖查询 facet 的**集合**"：
1. Stage 1 的 QueryContract 增加 facet/子问题分解（一份报告 #4 的延伸）；
2. 召回融合后做**带 facet 配额的贪心集合选择**（覆盖增益 + MMR 去冗 + 权威/时效项），替代分数求和；
3. Stage 6 大纲 = 证据集合对 facet 的覆盖规划；导出增加 **facet × evidence 覆盖矩阵**和**未覆盖 facet 清单**；
4. 未覆盖 facet 直接喂给 M2（声明局限/弃权）或 M4（一次有界扩展）——"系统明确说出自己漏了什么"。

**最小切片**：facet 用确定性规则 + LLM 契约两路（D1，失败回退单 facet）；集合选择是纯函数（TDD 友好：给定 facet/分数矩阵，断言选择结果的覆盖性质）；指标 facet coverage@K、冗余率、矩阵完整率；综述结构质量用 LitReview Arena 五维做 10–20 篇小样本人评。

**为什么是升级**：从"推荐的论文相关吗"到"**该被看到的子方向是否都被看到了**"——这是综述场景区别于问答场景的根本质量维度，2026 年才开始有正式评测语言，且与 D7–D9 的可信主张闭环（没证据的 facet 不乱写）。

---

### M7 证据台账与过程级评测：让"可验证性"成为可以交付的产物

**2026 证据**：
- **trajectory-judge**（arXiv 2609.00038，摘要已核）：向正确轨迹注入故障，发现只看请求+最终回复的 14B judge 对"回复毫无变化的沉默故障"仍有 34–76% 召回——必须用**配对判别**（故障轨迹 flag 率 − 干净轨迹 flag 率）才能戳穿虚报。
- 过程+结果双评：MiroEval（arXiv 2603.28407）；交互式：IDRBench（arXiv 2601.06676）。
- LLM-judge 可靠性批判（2026 密集）：Reliability without Validity（arXiv 2606.19544）、Dark Current 分层空判测试（arXiv 2606.15610）、BiasScope（arXiv 2602.09383）、CaLLM 校准判官（arXiv 2610.18108）。
- AquiLLM（arXiv 2609.16519）：面向**开源科研 RAG**的忠实度评测；LitReview Arena 五维专家协议；Deep Research 错误分析（arXiv 2610.29346）。

**升级主张**：系统已有 `trace_id` 与 `stage_results`，把它升级为每次运行导出一份**证据台账（evidence ledger）**：
`query/contract → facet → paper(元数据+来源通道) → span(+offset) → claim → 各介入点决策 → 面板判决 → 校准风险 → 终态（断言/弃权/修复）`。
在台账上同时做两层评测：
- **结果层**：Recall@K/MRR、citation P/R、claim 忠实度（沿用一份报告 #3）；
- **过程层（2026 差异化）**：介入决策正确率、护栏触发恰当性、修复成功率、证据脱离率（M4）、核验器分歧率（M3）；
- 每个 LLM 判官指标**强制配空判对照**（打乱/替换引用后判官是否还判"通过"——dark-current 控制），把判官自身的虚报率一并报告；
- 人评直接采用 LitReview Arena 风格：匿名、对战、五维（覆盖、准确、结构、溯源可用性、实用价值）。

**最小切片**：扩展 `graphs/streaming.py`/Stage 8 导出的 JSON schema（先写 schema 测试）；`tests/` 下离线评测脚本消费台账；一份人评表格模板（20–30 任务）。无新依赖。

**为什么是升级**：多数毕业设计只报最终文本的指标；交付**机器可读的过程证据 + 被校准过的判官协议**，直接呼应校训级别的"可验证性"，也是 M1–M6 所有数字的公信力底座。

---

## 3. 与三个 2026 对位系统的差异定位

| 维度 | OpenScholar（Nature 2026） | PaperQA2（2024） | Co-Scientist（Nature 2026） | **本系统升级后的主张** |
|---|---|---|---|---|
| 目标 | 科研问答+长答案综合 | 科研知识综合（检索/综述/矛盾检测） | 新颖假设生成（交实验验证） | **检索-可信综述-个性化推荐**，不主张发现 |
| 数据 | 4,500 万篇 OA 自建语料 | 给定语料 | 文献+工具 | 多源可替换（OpenAlex/arXiv/…，D 可替换性），无自建大语料 |
| 模型 | 8B 专用训练模型 | 通用 LLM | Gemini + test-time compute | 单一 OpenAI 兼容客户端（D1），**免训练、规则/统计为主** |
| 引用可信 | 固定 attribution model（2026 已被测出 3–18% 摆动） | 固定核验器 | 不作此主张 | **构造合法（M1）+ 面板审计（M3）+ 风险保证弃权（M2）** |
| 过程形态 | 单次检索综合 | RAG 式流水线 | 多智能体锦标赛 | 确定性流水线优先 + 有界条件介入（D2+M4），决策全留痕 |
| 覆盖性 | 长答案评测 | 无专门机制 | — | facet 覆盖矩阵+显式缺口（M6） |
| 个性化/推荐 | 无 | 无 | 无 | **跨会话记忆即推荐 + 可控新颖性（M5）** |
| 评测 | ScholarQABench | 人机对比 | 专家+实验 | 结果+过程双层、判官带空判对照（M7） |

一句话定位（可直接进论文相关工作章）：**OpenScholar/PaperQA2 证明了"带引用的科研综合"能做到什么水平；2026 年的审计证据表明其可信性度量本身不稳。本系统不追求更大的模型或更大的语料，而把可信度做成构造约束、统计保证与可审计过程，并补上它们都没有的个性化推荐半壁。**

---

## 4. 落地路线（与一份报告 Tier 1 交织，全部遵守 TDD）

1. 真实召回 OpenAlex（一份报告 #1）与 D9 span 落库（#6）——M1/M5/M6 的共同数据底座；
2. **M1 结构化契约 + 校验节点**——立刻让 D7 从提示升级为构造保证；
3. **M3 核验面板 → M2 conformal 门控**（即一份报告 #2 的升级版）；
4. 评测闭环（#3）与 **M7 台账**同步建设，此后每一步由回归数字把关；
5. QueryContract facet 化（#4）→ **M6 覆盖矩阵**；
6. 事件表 + 尾部推荐节点 → **M5**（兑现系统名称）；
7. **M4 步级介入 + 三臂消融**（#8 的升级版，作为"为什么需要 LangGraph"的架构证据）；
8. 成本三件套（#7）与 HyDE/两级重排（#4/#5）作为支撑性工程按余量插入。

M1+M3+M2+M7 构成最小"可信闭环"；M5/M6 是产品与论文章节差异；M4 是架构叙事。时间不够时的砍序：M4 可只做消融设计 + 单点实现，M5 可只做无 embedding 的确定性版本——但 M1/M2/M3/M7 不建议砍，它们共同支撑"可信性"这个论文主主张。

## 5. 论文写作映射（诚实标注）

- **可写成"本人设计与实现"并出数**：M1（契约+投影+修复）、M2（conformal 曲线）、M3（面板+分歧率）、M6（确定性集合选择+覆盖矩阵）、M7（台账+空判对照）。
- **设计 + 小规模实验**：M4（三臂消融依赖评测集）、M5（离线事件日志评测 + 小样本盲评）。
- **只能写未来工作**：RL 搜索/意图训练（Search-R1、IntentRL、O-Researcher、WebDancer/WebSailor）、Co-Scientist 式假设锦标赛、CKM 式滑窗文献代谢（arXiv 2604.12243，可作为 M5 时间维度的展望）、GraphRAG 个人语料。
- **写作红线**：① 商业 OpenAI 兼容端点不暴露 logits，不得声称"解码级保证"，措辞用"输出契约/构造约束"，受限解码作为方法学引用；② 所有 2026 预印本结论标注"预印本、未同行评审"；③ 3–18% 摆动等数字只可描述为**文献报告值**，本系统数字必须自测；④ OpenScholar 相关数字（4,500 万篇、2,967 查询、208 长答案）以 Nature 页面定稿前回源核对。

---

## 附录：本次新核实文献表（2026-11-02，均为一份报告 85 条之外的增量）

> ✅ = OpenAlex 全记录或列表记录当日实测；**摘要已核**= 读过摘要确认内容主张。引用量为当日快照，2026 新文普遍为 0–个位数。

| # | 文献（第一作者 et al.） | 日期 / venue | DOI / arXiv | 引 | 状态 |
|---|---|---|---|---|---|
| 1 | OpenScholar: Synthesizing scientific literature with retrieval-augmented LMs (Asai et al.) | 2026-02 / Nature | 10.1038/s41586-025-10072-4 | 38 | ✅ 摘要已核（未给 arXiv 号：记忆编号实测为无关论文） |
| 2 | Accelerating scientific discovery with Co-Scientist (Gottweis et al.) | 2026-05 / Nature | 10.1038/s41586-026-10644-y | 160 | ✅ 摘要已核 |
| 3 | IDRBench: Interactive Capabilities of Deep Research Agents | 2026-01 / arXiv | arXiv 2601.06676 | 0 | ✅ |
| 4 | MiroEval: Multimodal Deep Research Agents in Process and Outcome | 2026-03 / arXiv | arXiv 2603.28407 | 0 | ✅ |
| 5 | MMDeepResearch-Bench | 2026-01 / arXiv | arXiv 2601.12346 | 0 | ✅ |
| 6 | Benchmarking and Error Analysis of Deep Search and Deep Research LLM Agents | 2026-10 / arXiv | arXiv 2610.29346 | 0 | ✅ |
| 7 | Evaluating Deep Research Agents on Expert Consulting Work | 2026-05 / arXiv | arXiv 2605.17554 | 0 | ✅ |
| 8 | MiroFlow: Open-Source Agent Framework for General Deep Research | 2026-02 / arXiv | arXiv 2602.22808 | 0 | ✅ |
| 9 | O-Researcher: Open-Ended Deep Research via Multi-Agent Distillation and Agentic RL | 2026-01 / arXiv | arXiv 2601.03743 | 0 | ✅ |
| 10 | IntentRL: Proactive User-intent Agents for Open-Ended Deep Research | 2026-02 / arXiv | arXiv 2602.03468 | 0 | ✅ |
| 11 | Ares: Adaptive Reasoning Effort Selection for Efficient LLM Agents | 2026-03 / arXiv | arXiv 2603.07915 | 1 | ✅ |
| 12 | LLM Agents Already Know When to Call Tools — Even Without Reasoning | 2026-05 / arXiv | arXiv 2605.09252 | 0 | ✅ |
| 13 | ReaLM-Retrieve: When to Retrieve During Reasoning (Guo et al.) | 2026-04 / arXiv | arXiv 2604.26649 | 0 | ✅ 摘要已核 |
| 14 | Adaptive Retrieval helps Reasoning in LLMs — but mostly if it's not used (Shakya et al.) | 2026-02 / arXiv | arXiv 2602.07213 | 0 | ✅ 摘要已核 |
| 15 | Adaptive Retrieval for Reasoning-Intensive Retrieval | 2026-01 / arXiv | arXiv 2601.04618 | 0 | ✅ |
| 16 | R²-Searcher: Calibrating Retrieval and Reasoning Boundaries for Agentic Search | 2026-06 / arXiv | arXiv 2606.28566 | 0 | ✅ 摘要已核 |
| 17 | A-RAG: Scaling Agentic RAG via Hierarchical Retrieval Interfaces | 2026-02 / arXiv | arXiv 2602.03442 | 0 | ✅ |
| 18 | Scaling Retrieval-Augmented Reasoning with Parallel Search and Explicit Merging | 2026-05 / arXiv | arXiv 2605.13534 | 0 | ✅ |
| 19 | The Retrieval-Reasoning Paradox: Evidence Disengagement in a Reasoning-Augmented LM | 2026-04 / Zenodo | 10.5281/zenodo.19672442 | 0 | ✅（非同行评审预印本，引用时注明） |
| 20 | Retrieval-Infused Reasoning Sandbox: Decoupling Retrieval and Reasoning | 2026-01 / arXiv | arXiv 2601.21937 | 0 | ✅ |
| 21 | A Survey of Test-time Compute: From Intuitive Inference to Deliberate Reasoning | 2026 / Computational Linguistics | 10.1162/coli.a.629 | 3 | ✅ |
| 22 | FullCite: Explicit Evidence Grounding via Structured Inline Citation Generation (Yeginbergen et al.) | 2026-06 / arXiv | arXiv 2606.07130 | 0 | ✅ 摘要已核 |
| 23 | When Copying Is Hard: Copy-Constrained Decoding for Exact Span Reproduction | 2026-10 / arXiv | arXiv 2610.28393 | 0 | ✅ 摘要已核 |
| 24 | ATTRICITE: Open 4B Model for Citation Recovery + CITEALIGN dataset | 2026-09 / arXiv | arXiv 2609.14248 | 0 | ✅ 摘要已核 |
| 25 | Guaranteeing Knowledge Integration with Joint Decoding for RAG | 2026-04 / arXiv | arXiv 2604.08046 | 0 | ✅ |
| 26 | Conformal Factuality Control for Multi-Hop RAG (Rehman & Yeh) | 2026-09 / arXiv | arXiv 2609.38222 | 0 | ✅ 摘要已核 |
| 27 | Word-Level Conformal Risk Control for LLM-RAG Hallucination under Domain Shift (Lin) | 2026-01 / 期刊预印本 | 10.61424/ka6yps02 | 0 | ✅ 摘要已核（小刊，方法参考） |
| 28 | AB-RAG: Adaptive Budgeted RAG for Reliable QA (training-free) | 2026-06 / arXiv | arXiv 2606.29090 | 0 | ✅ 摘要已核 |
| 29 | Facet-Level Tracing of Evidence Uncertainty and Hallucination in RAG | 2026-04 / arXiv | arXiv 2604.09174 | 0 | ✅ |
| 30 | Towards Dependable RAG Using Factual Confidence Prediction | 2026-05 / arXiv | arXiv 2605.05244 | 0 | ✅ |
| 31 | RAGScope: Leakage-Controlled, Cost-Aware Evidence-Gating Protocol | 2026-09 / arXiv | arXiv 2609.39075 | 0 | ✅ |
| 32 | UR-RAG: Unified Risk Calibration for RAG | 2026-06 / Research Square | 10.21203/rs.3.rs-9985651/v1 | 0 | ✅（预印本服务器） |
| 33 | Evaluating and Guarding Citation Faithfulness in Agentic Scientific Synthesis (Goo et al.) | 2026-07 / arXiv | arXiv 2607.20527 | 0 | ✅ 摘要已核 |
| 34 | DeepSciVerify: Claim–Citation Alignment via LLM-Driven Evidence Escalation | 2026-05 / arXiv | arXiv 2605.27710 | 0 | ✅ 摘要已核 |
| 35 | HALLMARK: Diagnosing LLM Citation Verifiers and When to Deploy Them | 2026-07 / arXiv | arXiv 2607.18360 | 0 | ✅ |
| 36 | Verified Misguidance: Structural Citation Failures in Search-Augmented LLMs | 2026-05 / arXiv | arXiv 2605.28565 | 0 | ✅ |
| 37 | Retrieval Error or Generation Error? Hierarchical Failure Attribution + Evidence-Constrained Correction | 2026-01 / 期刊预印本 | 10.61424/besja393 | 0 | ✅ |
| 38 | Agent Memory as Recommendation: Recommender-System Design for Long-Term Memory of LLM Agents | 2026-10 / arXiv | arXiv 2610.34673 | 0 | ✅ 摘要已核 |
| 39 | HARPO: Hierarchical Agentic Reasoning for User-Aligned Conversational Recommendation | 2026-04 / arXiv | arXiv 2604.10048 | 0 | ✅ |
| 40 | Integrating Implicit Desire Fusion for Proactive Conversational Recommendation with LLMs | 2026-04 / Information Fusion | 10.1016/j.inffus.2026.104373 | 0 | ✅ |
| 41 | SPECTER-BS: Citation Recommendation with Bibliographic Scoring | 2026-01 / Knowledge and Information Systems | 10.1007/s10115-025-02677-y | 1 | ✅ |
| 42 | Citation Recommendation via SciBERT + Temporal-Aware GAT | 2026-09 / JUCS | 10.3897/jucs.176807 | 0 | ✅ |
| 43 | TextTAGC: Query-Oriented Scientific Paper Recommendation via Temporal-Aware GCN | 2026 / Scientometrics | 10.1007/s11192-025-05518-5 | 2 | ✅ |
| 44 | Serendipity-control, cognitive labelling and explanation in an LLM-based app (user study) | 2026-10 / Scientific Reports | 10.1038/s41598-026-78243-5 | 0 | ✅ |
| 45 | Recommendation Systems for Exploratory Data Tasks | 2026-09 / arXiv | arXiv 2609.39412 | 0 | ✅ |
| 46 | Personalization and Evaluation of Conversational Information Access | 2026-06 / arXiv | arXiv 2606.13717 | 0 | ✅ |
| 47 | RALI@iKAT 2026: Retrieval-aware User Profile Denoising for Personalized Conversational Dense Retrieval | 2026-10 / arXiv | arXiv 2610.17673 | 0 | ✅ |
| 48 | Agentic Conversational Search with Contextualized Reasoning via RL | 2026-01 / arXiv | arXiv 2601.13115 | 0 | ✅（RL，列未来工作） |
| 49 | Ko-WideSearch: Breadth-Search Benchmark for Exhaustive Set Enumeration by Web Agents | 2026-06 / arXiv | arXiv 2606.27595 | 0 | ✅ 摘要已核 |
| 50 | Scoring a Set, Not Summing Passage Scores: Set Retrieval | 2026-07 / arXiv | arXiv 2607.05712 | 0 | ✅ |
| 51 | CASI: Credit Assignment via Set Intervention for Agentic Retrieval | 2026-10 / arXiv | arXiv 2610.20293 | 0 | ✅ |
| 52 | EvidenceLens: A Claim–Evidence Matrix for Auditing Question Answering | 2026-06 / arXiv | arXiv 2606.23724 | 0 | ✅ |
| 53 | LitReview Arena: Battle-Style Evaluation of Literature Review Agents | 2026-07 / arXiv | arXiv 2608.21374 | 0 | ✅ 摘要已核 |
| 54 | trajectory-judge: What Outcome-Only LLM Judges Miss on Agent Trajectories | 2026-08 / arXiv | arXiv 2609.00038 | 0 | ✅ 摘要已核 |
| 55 | Reliability without Validity: Large-Scale Evaluation of LLM-as-a-Judge | 2026-06 / arXiv | arXiv 2606.19544 | 1 | ✅ |
| 56 | LLM Judges Have Dark Current: Stratified Null and Utility Tests | 2026-06 / arXiv | arXiv 2606.15610 | 0 | ✅ |
| 57 | BiasScope: Automated Detection of Bias in LLM-as-a-Judge Evaluation | 2026-02 / arXiv | arXiv 2602.09383 | 0 | ✅ |
| 58 | A CaLLM Judge is a Better Judge: Mitigating Bias in LLM-as-a-Judge | 2026-10 / arXiv | arXiv 2610.18108 | 0 | ✅ |
| 59 | AquiLLM: Faithfulness in Open-Weight RAG-LLM Systems for Scientific Research | 2026-09 / arXiv | arXiv 2609.16519 | 0 | ✅ |
| 60 | Continuous Knowledge Metabolism: Hypotheses from Evolving Literature (CKM) | 2026-04 / arXiv | arXiv 2604.12243 | 0 | ✅ 摘要已核（列未来工作） |
| 61 | Co-Reviewer: Agentic LLM–Human Alignment in Peer Review | 2026-02 / Scientometrics | 10.1007/s11192-026-05557-6 | 2 | ✅ |
| 62 | ScholarPeer: Context-Aware Multi-Agent Automated Peer Review | 2026-01 / arXiv | arXiv 2601.22638 | 0 | ✅ |
| 63 | PRISM: Multi-Dimensional Benchmark for LLM Peer Reviewers | 2026-05 / arXiv | arXiv 2605.26730 | 0 | ✅ |
| 64 | IntrAgent: Content-Grounded IR through Literature Review | 2026-04 / arXiv | arXiv 2604.22861 | 0 | ✅ |
| 65 | AgentSearchBench: AI Agent Search in the Wild | 2026-04 / arXiv | arXiv 2604.22436 | 0 | ✅ |
| 66 | Benchmarking Hybrid Deep Research Across Database Querying and Web Search | 2026-09 / arXiv | arXiv 2609.09410 | 0 | ✅ |

> 补充：dblp（HTTP 000）与 OpenReview（403）当日不可达；arXiv 主站限流。SIGIR/WWW/ACL/NeurIPS 2026 的正式出版版本可能与预印本编号并存，定稿引用前以出版方页面为准。
