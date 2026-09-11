# Vibe Coding Playbook

> 智能论文检索系统的 AI 辅助开发指南 — 毕业设计项目专用
> 整理自 Simon Willison 的实践方法论 + 本项目语境

---

## 📖 Part 1: Reading List (按使用场景分类)

### 🏛️ 基础篇 (Foundation) — 先读这三篇

#### 1. "Not all AI-assisted programming is vibe coding"
- 🔗 https://simonwillison.net/2025/Mar/19/vibe-coding/
- ⏱ ~8 min
- **核心:** AI 辅助编程的三种模式 — 权威式 (authoritarian) / Vibe coding / 代码库问答
- **何时读:** 第一篇必读，建立心智模型
- **关键句:** "我绝不提交无法向别人解释的代码"

#### 2. "Here's how I use LLMs to help me write code"
- 🔗 https://simonwillison.net/2025/Mar/11/using-llms-for-code/
- ⏱ ~12 min
- **核心:** Willison 的日常工作流
  - 函数签名口述 → 测试 → 修复 (标准循环)
  - Context is king — 管理对话上下文, 经常重开 chat
  - 用沙箱执行 (Code Interpreter, Artifacts, Claude Code)
  - 偏好"无聊的"稳定库 (避免训练截止后的新库)
- **何时读:** 第二篇,这是你的主要操作手册

#### 3. "Vibe engineering"
- 🔗 https://simonwillison.net/2025/Oct/7/vibe-engineering/
- ⏱ ~10 min
- **核心:** 生产级 AI 编程模式
  - **测试优先开发对 agent 特别有效**
  - 提前迭代计划,再交给 agent
  - 完善的文档 (agent 上下文有限)
  - 良好的版本控制 (agent 擅长 `git bisect`)
  - CI / 格式化 / Lint / Preview deployment
  - **核心论点:** "AI 工具放大现有专长"
- **何时读:** 第三篇,决定你的项目能否"毕业级"质量

---

### 🎙️ 实战篇 (Workflow) — 理解"我现在如何工作"

#### 4. "Highlights from agentic engineering on Lenny's Podcast"
- 🔗 https://simonwillison.net/2026/Apr/2/lennys-podcast/
- ⏱ ~15 min
- **核心数据点:**
  - **95% 的代码不是他自己敲的** — 甚至小的重构也委托给 agent
  - 每个功能通常建 **3 个原型** (原型现在"免费")
  - **测试是新瓶颈** — 一旦从"数周"缩到"数小时",验证成为限制步骤
  - 不再需要 2-4 小时不间断块 — 工作是"每过一会儿花 2 分钟提示 agent"
  - 持续探测能力边界 — 估时感"完全消失"
- **何时读:** 想理解 AI 时代的开发节奏时

#### 5. "More than just code review"
- 🔗 https://simonwillison.net/2026/Aug/22/more-than-just-code-review/
- ⏱ ~6 min
- **核心:** 验证技能比代码审查更重要
  - 自信地指示 agent 改动
  - 自信地验证改动是否真的应用
  - "逐行审查代码从来不是验证变更最有效的方式"
  - 测试 / 运行时检查 / 语义验证可优于 code review
- **何时读:** 觉得 review diff 很累时

#### 6. "Conceptual integrity and counting lines of code"
- 🔗 https://simonwillison.net/2026/Aug/19/conceptual-integrity-and-counting-lines-of-code/
- ⏱ ~7 min
- **核心:** 警告 — 廉价的 AI 生成功能会侵蚀代码库的"概念完整性"
- **核心句:** "一切都回到纪律"
- **何时读:** 感觉代码在失控膨胀时

---

### 🛠️ 案例篇 (Examples) — 看具体怎么干活

#### 7. "Vibe coding SwiftUI apps is a lot of fun"
- 🔗 https://simonwillison.net/2026/Mar/27/vibe-coding-swiftui/
- ⏱ ~8 min
- **价值:** 完整走查一次 vibe coding 流程 — 发什么 prompt、怎么迭代、何时放弃

#### 8. "Vibe scraping and vibe coding a schedule app entirely on my phone"
- 🔗 https://simonwillison.net/2025/Jul/17/vibe-scraping/
- ⏱ ~10 min
- **价值:** 证明"瓶颈不再是编码速度",在手机上也能完成完整项目

#### 9. "JustHTML is a fascinating example of vibe engineering in action"
- 🔗 https://simonwillison.net/2025/Dec/14/justhtml/
- ⏱ ~6 min
- **价值:** 一个生产级 vibe engineering 项目的范例

#### 10. "Useful patterns for building HTML tools"
- 🔗 https://simonwillison.net/2025/Dec/10/html-tools/
- ⏱ ~12 min
- **价值:** 快速搭 Demo UI 的模式 (你的 RAG 系统可能需要)

---

### ⚠️ 概念辨析篇 (Conceptual) — 避免误用术语

#### 11. "Two publishers and three authors fail to understand what 'vibe coding' means"
- 🔗 https://simonwillison.net/2025/May/1/not-vibe-coding/
- ⏱ ~5 min
- **价值:** 厘清 vibe coding 不是什么 — 对写论文"方法"章节有用

#### 12. "Vibe coding and agentic engineering are getting closer than I'd like"
- 🔗 https://simonwillison.net/2026/May/6/vibe-coding-and-agentic-engineering/
- ⏱ ~6 min
- **价值:** 理解当前最佳实践的边界

---

## 🎯 Part 2: Daily Cheat Sheet (每天真正会用到的)

### Willison 的三种 AI 编程模式

| 模式 | 何时用 | 你的角色 | 你的项目应用 |
|---|---|---|---|
| **Authoritarian (权威式)** | 生产代码 / 论文系统 | 架构师 + 评审 | 主体开发 |
| **Vibe Coding** | 学习 / 探索 / 一次性脚本 | 旁观者 | 快速原型 / 数据探索 |
| **Codebase Q&A** | 读陌生代码 / 理解设计 | 学习者 | 读 OpenAlex / LlamaIndex 源码 |

**黄金法则:** 绝不提交你无法向别人解释的代码

---

### 标准开发循环 (The Canonical Loop)

适用于每个功能、bug 修复、refactor:

```
1. SPEC     → 写清楚要做什么 (1-3 句)
2. SKELETON → 让 AI 写出函数签名 + 类型 + 文档字符串
3. TESTS    → 让 AI 写测试 (test-first 在 agent 场景特别有效)
4. IMPL     → 让 AI 写实现去通过测试
5. RUN      → 运行,看真实输出
6. FIX      → 把错误贴回给 AI
7. REVIEW   → git diff — 不接受盲改
8. COMMIT   → 单次提交一个绿色功能
```

---

### 高效 Prompt 模板

#### 模板 A: 新功能
```markdown
# Goal
<一句话目标>

# Context
- 现有文件: <列出>
- 技术栈: <Python 3.12, LlamaIndex 0.12, Qdrant 1.10, DeepSeek API>
- 代码风格: 参考 src/ingest/openalex.py — 不要用类,用函数

# Constraint
- 不引入新依赖
- 完整类型提示
- 用 logging,不用 print

# Done when
- <可验证的结果,例如:运行 ingest 命令能处理 100 篇论文>
```

#### 模板 B: Bug 修复
```markdown
# Bug
<现象: 输入 X 期望 Y 实际得到 Z>

# Repro
```
<最小复现代码>
```

# Error
```
<完整 stack trace>
```

# Hypothesis
<你已经检查过什么>

# Environment
- OS: Windows 11
- Python: 3.12
- 已运行 `pytest tests/`,其他测试都通过
```

#### 模板 C: 读陌生代码
```markdown
我要把 <库名> 接入项目。请用 200 字解释:
1. 它怎么组织模块
2. 我应该扩展哪里来加 <我的功能>
3. 有哪些"陷阱"(常见错误用法)
不要改任何代码,只解释。
```

#### 模板 D: Refactor
```markdown
重构 <文件>:
- 目标: <例如"把 5 个相似函数合并为一个参数化函数">
- 约束: 行为不能改变,所有现有测试必须通过
- 范围: 仅改这一个文件
执行后用 pytest 验证。
```

---

### 项目规则 (粘到 CLAUDE.md)

```markdown
# Project Rules — 智能论文检索系统

## Style
- 完整 Python 类型提示
- 用 logging,不用 print
- 函数式优于类 (除非有明确状态)
- 每个文件顶部 docstring 说明用途

## Tests
- 测试在 tests/, 镜像 src/ 结构
- 每个新功能必须有测试
- Bug 修复: 先加失败测试,再修

## Commits
- 约定式提交 (conventional commits)
- 一次提交一个绿色功能
- 不提交失败的测试

## Deps
- 谨慎添加新依赖,需要时在 PR 说明理由
- 优先选"无聊的"稳定库 (训练截止后 1 年内的新库要警惕)

## AI Use
- 不提交无法向导师解释的代码
- 始终 git diff 检查改动
- prompt 历史保留 (写论文"方法"章节要用)
```

---

### 反模式 (Anti-Patterns)

| ❌ 不要 | ✅ 改用 |
|---|---|
| "帮我做个论文搜索系统" | "写 src/ingest/openalex.py:用 httpx 拉 2020-2025 CS 论文,保存到 JSONL,处理 rate limit" |
| 一次 prompt 写整个系统 | 一次一个模块,每个跑通再下一步 |
| 接受所有 AI 输出 | 永远 git diff + 跑测试 |
| 让 AI 选架构 | 写 SPEC.md, AI 实施 |
| AI 写完就 commit | 至少读 30% 关键路径 |
| 一个 session 写 1000 行 | 90 分钟封顶, commit, 走开 |
| 多个工具同时用 | 先吃透一个 2 周 |

---

## 🛠️ Part 3: 本项目工作流 (Specific to Your Thesis)

### 推荐工具栈
- **AI 助手:** Claude Code (你正在用) / Cursor (IDE 切换时)
- **LLM (项目用):** DeepSeek-V3 (便宜) / Claude Sonnet 4.5 (质量) / Qwen3 (中文)
- **Embedding:** BGE-M3 (中英双语, 长文档)
- **Reranker:** BGE-reranker-v2-m3
- **Vector DB:** Qdrant
- **RAG 框架:** LlamaIndex (索引强) / DSPy (prompt 优化)

### 6 周开发计划 (毕业 2027.5,反推)

| 周 | 任务 | AI 提示关键 |
|---|---|---|
| W1 | SPEC.md + 项目脚手架 | "按 docs/SPEC.md 搭项目结构" |
| W2 | OpenAlex 抓取 + 清洗 | "写 OpenAlex 抓取脚本,处理 rate limit" |
| W3 | BGE-M3 嵌入 + Qdrant 索引 | "写嵌入脚本,512 token 分块" |
| W4 | Hybrid 检索 (BM25 + dense) + BGE rerank | "写 hybrid retriever,RRF 融合" |
| W5 | LLM 生成 + 引用导出 | "写 answer 生成,每个 claim 必须有引用" |
| W6 | RAGAS 评估 + 论文图表 | "写评估脚本 + 50 query 黄金集" |

### 论文"方法"章节可直接借用的术语
- "Agentic Engineering" (Willison 2025) — 你用它来描述"AI 辅助开发流程"
- "Authoritarian Mode" vs "Vibe Coding" — 区分你项目的两类开发任务
- "Test-First Development with Agents" — 你的测试驱动开发方法
- "Specification-Driven Development" — 你的 SPEC.md 流程
- 引用 Simon Willison 的博客作为参考 (信通院/工业界常用的工业实践)

---

## 📌 快速参考卡 (贴到桌面)

```
WORKFLOW:
  1. Spec   → 写 SPEC.md
  2. Test   → 先写测试
  3. Prompt → 发给 AI
  4. Diff   → 读改动
  5. Run    → 跑测试
  6. Commit → 提交

GOLDEN RULE:
  不提交无法解释的代码

WHEN TO USE WHAT:
  生产代码     → Authoritarian (你设计, AI 写)
  探索/原型    → Vibe coding (放手)
  读陌生代码   → Codebase Q&A

DAILY:
  - 90 分钟一节
  - 每节一个绿色 commit
  - 每天 git status
```

---

**Last updated:** 2026-08-28
**Source:** Simon Willison 博客 (simonwillison.net) 精选 12 篇
**项目:** 面向复杂学术查询的智能论文检索与推荐系统
