# Agent Design Risk Review — Concerns & Solutions

> **Scope**: Design-level review of the system described in `Opening_Report_EN.md` (§4.2 requirements, §4.3 outline design), cross-referenced against production research in `Production_Concerns_RAG_Agents.md` (§1–§10).
> **Method**: Walk each module of the proposed pipeline, identify what can go wrong in production, why, and the concrete fix — mapped to your existing data model (`Paper`, `SearchRecord`, `EvidenceChunk`) where possible.
> **Date**: 2026-09-06

**Design recap** (the pipeline under review):

```
User query
  → [1] Query Understanding & Rewriting (LLM → QueryContract + variants)
  → [2] Multi-source Recall (Semantic Scholar / OpenAlex / arXiv + FlagEmbedding vectors)
  → [3] Dedup (title normalization) → RRF Fusion → Citation-Network Expansion → Light Filter
  → [4] Semantic Re-rank (BGE-Reranker)
  → [5] Evidence Extraction (chunking → EvidenceChunk)
  → [6] Survey Generation (intent template → numbered citations)
  → [7] Citation Verification (every [N] resolves to an EvidenceChunk)
  → [8] Export (BibTeX / RIS / GB/T 7714)
```

Each numbered stage below gets its own risk table.

---

## 1. Query Understanding & Rewriting

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 1.1 | **LLM mis-parses constraints** — wrong year, wrong venue, missed "exclude surveys" | Free-form NL → structured fields is error-prone; NVInfo production measured 3.2% query-rewrite error rate, and pre-retrieval errors **cascade** into every later stage | Garbage in, garbage out: the whole pipeline faithfully executes a wrong contract | (a) Validate the `QueryContract` with Pydantic enums + cross-field rules (e.g., `year_from ≤ year_to`); (b) add a **confidence score** per extracted field from the LLM; (c) below threshold → ask the user one clarification question instead of guessing; (d) log `raw_query ↔ contract` pairs for offline audit |
| 1.2 | **Query rewriting drifts intent** — variants recall the wrong topic | Synonym expansion optimizes lexical coverage, not intent | Recall inflation with precision collapse; rerank then can't rescue it | Add an **intent-preservation check**: embed the original query and each variant; reject any variant with cosine similarity < 0.75 to the original. Keep the original query as an always-on recall channel (never replace it) |
| 1.3 | **No clarification mechanism** — ambiguous queries ("recent papers on attention") are executed as-is | Design treats every query as fully-specified | "Recent" means 2026? 2023? User gets an arbitrary answer | Detect underspecified fields (year, venue, intent) → return a structured clarification card (UI chips the user clicks), rather than one free-text question. Cap at 1 clarification round to avoid friction |
| 1.4 | **No multi-turn memory** — "same thing but from 2024+" starts a brand-new task | `SearchRecord` has no session/lineage concept | Real research workflows are iterative; forcing full re-entry kills usability | Add `session_id` + `parent_record_id` (self-FK) to `SearchRecord`; resolve anaphoric filters at the query-understanding stage by joining the parent contract. This is cheap and makes the demo dramatically better |
| 1.5 | **Contract rigidity** — constraints the schema doesn't model get silently dropped | `QueryContract` has fixed fields (topic/year/method/dataset/venue/exclusions) | User intent like "papers that *replicate* X" has nowhere to live, so it's lost before retrieval | Add a free-text `additional_constraints` field carried through retrieval as a soft reranking signal, and surface it in the response ("we also looked for: …") so the user can verify |

---

## 2. Multi-Source Recall (S2 / OpenAlex / arXiv + Vectors)

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 2.1 | **Straggler sources block the pipeline** — you `await` all 4 channels; arXiv is slow today | Parallel fan-out with a single join point | One slow API blows the 3 s P95 retrieval target for *every* query | **Per-source deadline budget** (e.g., 1.2 s). Use `asyncio.wait(..., timeout=...)` and proceed with whatever returned. Record `sources_completed` in `SearchRecord.filters` so results are honest about coverage ("degraded: arXiv skipped") |
| 2.2 | **Heterogeneous metadata quality** — OpenAlex lacks abstracts for some records; S2 citation counts lag; arXiv versions churn | Different providers, different schemas and update cadences | Bad metadata → bad dedup, bad rerank features, wrong citations in export | Build a **normalization layer**: canonical `Paper` upsert keyed by DOI (fallback: arXiv ID, then normalized title). Field-level merge policy: prefer the freshest non-null value; keep `source` array, not a single string (your `Paper.source VARCHAR(64)` should become a JSON array) |
| 2.3 | **Title-based dedup misses versions** — arXiv preprint vs published version vs v2 retitles | Title normalization can't catch "Title (extended version)" or subtitle changes | Duplicate papers inflate the candidate list and split citation counts across duplicates | Three-tier dedup: (1) DOI match → merge; (2) arXiv-ID ↔ DOI cross-lookup (S2/OpenAlex expose this) → merge; (3) normalized-title + first-author + year fuzzy match (≥ 0.9) → merge with a `merged_from` audit field |
| 2.4 | **RRF treats all sources as equally trustworthy** | RRF is rank-based only | A spammy/noisy source's rank-1 result outranks S2's rank-3 | Weighted RRF: per-source weight `w_s` (configurable; start equal, tune on eval set). Log per-source contribution to the top-10 so you can *see* source bias instead of guessing |
| 2.5 | **Citation-network expansion explodes** — snowballing references/被引 can triple the candidate set | One expansion round on 50 papers = hundreds of new candidates | Latency, token cost, and rerank load balloon; P95 target dead | Hard caps: expansion breadth ≤ 5 refs per paper, 1 round only, budget ≤ 30 new candidates, and only expand papers that survived dedup+RRF (top-20). Mark expanded papers with `origin='citation_expansion'` so evaluation can measure whether expansion actually helps |
| 2.6 | **Vector index silently rots** — embedding model upgraded, or papers retracted | Index built once; no refresh loop in the design | Stale/misaligned results; §10.1.2 of the concerns doc: embedding drift is a Strong-grade production failure | (a) Store `embedding_model` + `embedding_version` per index; refuse queries across versions; (b) daily arXiv refresh, weekly S2/OpenAlex; (c) retraction tombstones (Crossref retraction API) applied at query time — never delete, flag |

---

## 3. Filtering & Re-Ranking

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 3.1 | **The "lightweight filter" is under-specified** — trained on what? | Design says "轻量级过滤模型" without a data source | Either it's an LLM call (cost + latency) or an untrained heuristic (unpredictable) | Cheapest credible option: **embedding-similarity threshold filter** (query embedding vs paper embedding, cut at ~0.5) + rule-based cuts (retracted, year-out-of-range). Zero training data needed, deterministic, testable. Log filter kill-reason per paper |
| 3.2 | **Rerank can't fix recall** | Reranker only reorders *already-recalled* candidates (the #1 caveat from §10.2 of the concerns doc) | Team tunes rerank for weeks while the real problem is recall | Put **Recall@K before and after every stage** into the eval harness; decide tunings by which stage's metrics move. Alert rule: if rerank ΔnDCG < 0.02 but end-to-end is bad, the problem is upstream |
| 3.3 | **Expansion results dominate the final ranking** | Citation-expanded papers enter RRF late and rerank sees them fresh | Top-10 floods with "generally famous" papers, not query-relevant ones | Feed expanded papers through the same light filter + rerank as everyone else (no free pass), and cap their share of the final top-N (e.g., ≤ 40%) until eval data says otherwise |
| 3.4 | **Multi-objective ranking (authority/timeliness/relevance/diversity) has no defined fusion** | Design lists the objectives but not the math | Underspecified = untestable; scores drift with every prompt tweak | Define an explicit scoring function: `final = α·relevance + β·norm(log citations) + γ·recency + δ·diversity(MMR)`, with α–δ as config. Expose the **top-3 feature contributions** per paper in the UI as the "ranking reason" — this satisfies the proposal's explainability requirement *and* makes tuning observable |

---

## 4. Evidence Extraction & Chunking

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 4.1 | **Abstract-only evidence** — S2/OpenAlex APIs return abstracts, not full text | Full text requires publisher access | Evidence is thin; surveys built only from abstracts are shallow — a reviewer of your thesis *will* notice | Be deliberate: (a) for arXiv papers, pull full text (open access) and chunk by section — matches your `EvidenceChunk.section` field perfectly; (b) for closed-access, explicitly label evidence as `abstract_only` in the `section` field and say so in the UI. Honest limitation > silent shallowness |
| 4.2 | **Chunking strategy unspecified** | Design says "语义分块" without the algorithm | Fixed-token splitting breaks sentences/tables (Strong-grade failure, §10.1.1); chunks split answers across boundaries → unreachable recall ceiling | Section-aware chunking for academic text: split on section headers first, then paragraph, then pack to ~400–600 tokens with **15–20% overlap**. Keep `anchor` = (section, paragraph index) — it's already in your schema |
| 4.3 | **LLM-based evidence selection hallucinates the selection itself** | The extractor is also an LLM | It "finds" evidence that isn't in the paper, or picks chunks for the wrong claim | Constrain extraction to **extractive quotes**: prompt the LLM to return verbatim spans + offsets from the given chunk; verify the span exists in the source text (string/normalized match) before writing `EvidenceChunk`. Reject anything that doesn't verify — never let the extractor paraphrase into the evidence store |
| 4.4 | **Evidence extraction cost is O(papers × chunks)** | One LLM call per candidate paper for evidence location | 50 papers × 1 call = latency + cost blows the 10K token/query budget | Two-tier: embed the query, score every chunk by cosine similarity, LLM-verify only the **top 3 chunks per paper** for top-10 papers. That's ~30 verification calls max; the rest is local math |
| 4.5 | **`anchor` fragility** — "page 3, paragraph 2" rots when the source re-renders | Anchors computed against one rendering of the paper | Citation links break; verification can't re-locate the span | Store the **verbatim span itself** as the anchor's fallback (`content` already holds it), plus offsets when available. Re-locate by string search at render time, not by stored page number |

---

## 5. Survey Generation

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 5.1 | **Citation-number mapping is the classic failure point** | LLM must map "evidence #4" → "[4]" in prose; it invents numbers, skips them, or misattributes | Even with verification, bad mapping = regeneration loops = latency | Don't let the LLM invent numbers: give it chunks **pre-numbered [1]…[N] in the prompt**, instruct "cite only these numbers", then post-process: any `[k]` where k > N or uncited-chunk → trigger **one** repair regeneration with the violation list appended. Two strikes → fall back to per-claim evidence cards (no flowing prose) |
| 5.2 | **No faithfulness check before output** | Verification (stage 7) checks existence, not support | A claim can cite a *real* chunk that doesn't actually support it | Add a **support check**: for each (claim, cited chunk) pair, semantic entailment via embedding similarity (cheap) on the generated claim vs chunk content; below threshold → flag the sentence with a warning badge, don't silently drop it. This is the `is_reliable` pattern from §10.4 of the concerns doc, applied to output |
| 5.3 | **Template selection errors** — wrong intent → wrong output shape | Intent classifier (part of stage 1) can misroute | A "compare methods" request gets a trend narrative | Let the LLM declare intent as a structured field with confidence (same pattern as 1.1); show the chosen template in the UI *before* generation so the user can switch. Cheap, and doubles as a demo feature |
| 5.4 | **Token budget vs evidence context conflict** — 10K budget ÷ (system prompt + 8 chunks + instructions) is tight on big surveys | Design sets a 10K budget but generation wants more context | Truncated chunks mid-survey; quality cliff | Budget accounting at prompt-assembly time: system ≤ 1K, per-chunk ≤ 600, reserve ≥ 2K for output. If over → drop lowest-ranked chunks (log it), never truncate a chunk mid-text |
| 5.5 | **Conflicting evidence unresolved** (Strong-grade failure) | Two papers disagree; the LLM blends them into false consensus | Survey asserts what the field actually disputes | Instruct generation to surface disagreement explicitly ("X reports A; Y reports B; the difference may be due to…"), and add a UI marker on sentences whose cited chunks have low mutual similarity |

---

## 6. Citation Verification (Stage 7)

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 6.1 | **Existence ≠ support** | Design verifies `[N]` resolves to a chunk — but not that the chunk *backs the claim* | "Verified" badge becomes a false trust signal | Two-level verification, exposed separately in the UI: **L1 exists** (resolves to EvidenceChunk) → green; **L2 supports** (entailment/similarity check, 5.2) → gold. Unverified L2 → amber badge + "review suggested". This gradation *is* your thesis's evidence-trustworthiness story |
| 6.2 | **Verification is on the critical path** | Every output waits for verification | Adds latency to an already-60 s pipeline | Verify **during** streaming: as each sentence completes, check its citations; stream the badge with the sentence. Total pipeline latency unchanged |
| 6.3 | **Verification failures have no recovery path** | Design says "给出警告标识" and stops | User gets a broken survey and must fix it manually | Recovery ladder: (1) repair-regeneration once (5.1); (2) if still failing, **drop the sentence** and note the omission; (3) if > 30% of sentences fail, abort prose mode and emit structured evidence cards. Log which rung fired — that's your failure-rate metric |

---

## 7. Data Model & Storage

| # | Concern | Why It Happens | Impact | Solution |
|---|---|---|---|---|
| 7.1 | **SQLite under 100 concurrent users** | Design specifies SQLite + 100 peak concurrency | Write contention (Strong-known failure mode; §9.8 of concerns doc); P95 targets die under load | WAL mode + connection pooling + single-writer discipline for the prototype; **design the DAL so Postgres is a config swap** — then the 100-user claim is defensible in a viva ("the schema and access layer are portable; SQLite was a scoped prototype decision") |
| 7.2 | **`SearchRecord.result_paper_ids TEXT`** | JSON blob in a TEXT column | Can't query "which searches returned paper X"; no integrity | Keep it for reproduction (that's its stated purpose), but add a join table `search_result_items(record_id, paper_id, rank, score_breakdown)` — the `rank` + `score_breakdown` columns double as your ranking-audit log, which the eval harness (§9) needs anyway |
| 7.3 | **No user/tenant model** despite admin features mentioning "用户与权限维护" | Data model has 3 tables; users aren't one of them | Can't do row-level isolation (security concern §10.6) or per-user cost caps | Minimal: `User(id, role, budget_cap)` + `user_id` FK on `SearchRecord` and `EvidenceChunk`. Row-level scoping enforced in the DAL, asserted by an integration test — this is a half-day of work that closes a real security gap |
| 7.4 | **No audit/cost ledger** | Cost attribution isn't in the schema | Can't honor "Token 成本" as an evaluation metric (it's in your own proposal §1) | `llm_call_log(trace_id, stage, model, tokens_in, tokens_out, cost_usd, latency_ms, created_at)`. One table powers: cost dashboards, per-stage latency traces, and the "API 调用次数" metric — highest ROI table in the system |

---

## 8. Non-Functional Targets vs. Design Reality

| # | Concern | The Conflict | Solution |
|---|---|---|---|
| 8.1 | **60 s end-to-end × 100 concurrent × LLM provider limits** | 100 users × multi-LLM-call pipeline ≫ any provider's concurrency allowance; the design has no queueing story | Job queue from day one: task POST → `task_id` (Arq/RQ) → SSE progress. Global LLM semaphore (e.g., 8), per-user queue, 503 + `Retry-After` at saturation. The proposal's own "阶段性结果" phrasing already implies this — make it explicit in the design |
| 8.2 | **"测试覆盖率 ≥ 95%" vs LLM nondeterminism** | Coverage is achievable for deterministic modules; LLM stages can't be "covered" meaningfully | Reframe honestly in the thesis: ≥ 95% coverage on **deterministic modules** (dedup, RRF, formatting, verification logic); LLM stages get **eval-metric gates** (golden set, faithfulness thresholds) instead of coverage. This is the *more* sophisticated engineering position, not a weaker one |
| 8.3 | **Multi-objective P95 targets lack per-stage attribution** | "P95 ≤ 3 s retrieval" is unactionable without stage-level spans | trace_id already exists in stage 1 — **propagate it through every stage** and record per-stage spans into `llm_call_log` (7.4). Now "which stage broke the P95" is a query, not an investigation |
| 8.4 | **Effectiveness testing (效果测试) has no dataset** | Proposal says human eval + Recall@K, but defines no corpus/queries | Build the **golden set of 50 queries** (papers + evidence chunks hand-labeled) as a versioned repo artifact; run it nightly. It powers Recall@K, faithfulness regression, and the thesis's experiment chapter simultaneously |

---

## 9. Pipeline-vs-Agent Gap (Design-Level Decision)

Your proposal describes a **fixed pipeline**; the agent-pattern ideas (plan-first, tool-use loop) live only in `Resume_Shining_Points.md`. This is a real fork in the road:

| Option | Pros | Cons | When |
|---|---|---|---|
| **A. Keep the fixed pipeline** (as proposed) | Deterministic, testable, every stage auditable — *exactly* what a thesis wants; predictable latency/cost | Less impressive to "agent engineer" job postings; can't handle open-ended queries | Default. Ship this. |
| **B. Agent-wrapped pipeline** (pipeline stages become tools; LLM decides order/repetition) | Handles messy queries ("find the dataset X uses, then find papers replicating it"); agent-engineer resume story | Non-determinism, loop risk, cost variance, harder evaluation | Add **after** the pipeline works, as a mode: `mode=agent` where the planner can invoke the pipeline stages as tools with hard caps (≤ 8 steps, fingerprint loop detection per §10.4) |

**Recommendation**: A first, B as a bounded add-on. The pipeline's determinism is what makes your evaluation chapter rigorous; the agent mode then becomes "and we extended it" — a strong closing chapter instead of an unfinished core.

---

## 10. Priority Matrix

| Priority | Item (§ above) | Why This Order |
|---|---|---|
| 🔴 P0 — do first | 2.1 per-source deadlines · 5.1 citation mapping + repair · 7.4 `llm_call_log` · 8.1 task queue | These break the headline P95/cost promises or the core trust story; all are days-level work |
| 🟠 P1 — before eval chapter | 8.4 golden set · 3.2 stage-wise Recall@K · 6.1 two-level verification · 4.3 extractive-quote constraint | Your thesis's experimental rigor depends on these existing |
| 🟡 P2 — quality & depth | 4.1/4.2 full-text + section chunking · 5.2 faithfulness check · 2.3 three-tier dedup · 1.2 intent-preservation check | Meaningful quality lifts; each has a measurable before/after for the thesis |
| 🟢 P3 — polish | 1.4 session memory · 7.3 user model · 2.4 weighted RRF · 3.4 scoring function exposure · 9B agent mode | Differentiators once the core is solid |

---

> **Companion files**: `Opening_Report_EN.md` (design source) · `Production_Concerns_RAG_Agents.md` (failure-mode reference, §1–§10) · `Resume_Shining_Points.md` (roadmap)
