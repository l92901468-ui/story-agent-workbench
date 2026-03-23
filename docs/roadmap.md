# Roadmap（分阶段实现顺序）

本文档定义 Story Agent Workbench 在当前约束下的**优先实现顺序**。

目标：
- 先完成可验证的小闭环
- 再逐步扩展能力
- 明确“现在做什么 / 后面做什么 / 暂时不做什么”

适用前提：
- Python first
- low dependency
- 文档与代码同步
- 不过度设计

---

## 阶段 1：文档与路线稳定（当前优先）

### 目标
- 把项目意图、模块边界、实现顺序写清楚，避免协作者理解偏差。

### 具体任务
1. 对齐 `README.md`、`PROJECT_SPEC.md`、`docs/architecture.md` 的叙述。
2. 新增并维护本文件 `docs/roadmap.md`。
3. 明确短期非目标（GraphRAG 全实现、数据库、多 agent、UI）。
4. 为后续开发约定术语：canon / draft / reference / structured registry。

### 验收标准
- 新协作者只读文档即可回答：
  - 项目解决什么问题
  - 当前阶段做什么
  - 下一阶段按什么顺序推进
- 文档之间没有明显冲突。

### 暂时不做什么
- 不新增复杂实现代码。
- 不引入依赖。

---

## 阶段 2：最小文本接入闭环（loader/chunker）

### 目标
- 让本地叙事资料（txt/md）能被稳定读取并切分，为检索做输入准备。

### 具体任务
1. 在 `src/story_agent_workbench/ingest/` 建立最小 loader：读取本地 txt/md。
2. 实现简单 chunker（例如固定长度 + 重叠）。
3. 设计最小元数据结构（来源文件、段落编号、数据层标签）。
4. 给出输入目录规范与命名示例（文档说明即可，不需数据库）。

### 验收标准
- 能对一个小样本语料执行：读取 → 切分 → 输出可检查的 chunk 列表。
- chunk 输出包含最小元数据（source/chunk_id/layer）。
- 过程可在本地 CLI 或脚本中复现。

### 暂时不做什么
- 不做复杂文档解析（PDF/网页等）。
- 不做分布式索引或外部存储。

---

## 阶段 3：最小普通 RAG

### 目标
- 基于阶段 2 的 chunk 数据，实现可演示的普通检索问答闭环。

### 具体任务
1. 在 `retrieval/text_retriever.py` 实现最小检索逻辑（可先关键词/BM25-like/简单向量占位）。
2. 约定检索输入输出结构（query、top_k、results、evidence）。
3. 在 `main.py` 打通用户问题到文本检索结果返回。
4. 增加“证据片段展示”字段，便于人工校验。

### 验收标准
- 对局部问题（找句子、找相关片段）能返回可读结果。
- 每条结果能追溯来源文本。
- 输出结构稳定，便于后续路由层复用。

### 暂时不做什么
- 不追求生产级召回与排序质量。
- 不实现复杂重排模型或在线服务化。

---

## 阶段 4：最小图结构占位

### 目标
- 在不实现完整 GraphRAG 的前提下，建立图查询接口与最小结构约定。

### 具体任务
1. 在 `graph/graph_retriever.py` 明确输入/输出 schema。
2. 定义最小图实体类型：角色、地点、阵营、事件、时间锚点。
3. 用纯 Python 数据结构维护小型样例图（占位实现）。
4. 支持 1~2 类最小查询（如“角色关系邻接”“阵营关联”）。

### 验收标准
- 路由到图检索时返回结构化结果而非空占位。
- 结果可解释（节点、边、来源依据可读）。
- 代码保持低复杂度，便于后续替换为正式 GraphRAG。

### 暂时不做什么
- 不做自动关系抽取流水线。
- 不接图库数据库（Neo4j 等）。

---

## 阶段 5：路由与回复策略层

### 目标
- 从“只有路由规则”升级为“路由 + 回复策略 + 证据展示 + 回退逻辑”的统一策略层。

### 具体任务
1. 将路由触发关键词与阈值配置化（text/graph）。
2. 路由输出统一包含：`route` / `reason` / `confidence`。
3. 将 mode 选择策略化：默认 chat，仅在意图明确时自动切换到 feedback/critic/evidence。
4. 统一 evidence 展示策略：默认轻量引用，只有 evidence 模式或显式开关展示完整证据。
5. 增加回退策略：
   - graph 弱命中回退 text
   - 两边都弱时给不确定性提示，不假装确定

### 验收标准
- 行为可通过配置文件调整，而不必改核心逻辑。
- route 决策可解释（含 confidence 分值）。
- 四种回复模式职责边界清楚、可复现。
- 非 evidence 模式默认不刷屏，但可看到轻量引用。
- 有明确弱命中回退路径。

### 暂时不做什么
- 不做复杂意图分类模型。
- 不做多 agent 协调器。

---

## 阶段 6：测试与样例完善

### 目标
- 建立“可重复验证”的基础质量保证，降低后续迭代风险。

### 具体任务
1. 增加最小测试集：
   - loader/chunker 行为测试
   - text retriever 基础行为测试
   - router 分流测试
2. 提供 `examples/` 或文档化示例输入输出。
3. 增加一份“手动验收清单”（面向新手）。
4. 在 README 中补充运行与验证步骤。

### 验收标准
- 关键路径有可执行测试或等价校验脚本。
- 新协作者可按文档在本地复现实验结果。
- 常见失败场景有说明（如空输入、找不到文件）。

### 暂时不做什么
- 不追求大规模 benchmark。
- 不引入复杂 CI/CD 体系（可后续再加）。

---

## 阶段 7：未来阶段（增量推进）

### 7A 隐藏式多 agent 编排（当前子阶段）

#### 目标
- 在不做前台群聊 UI 的前提下，支持后台多角色协作。

#### 具体任务
1. 增加 orchestrator 调度层。
2. 至少支持内部角色：story_buddy / critic / systems_designer / builder。
3. 保持外部单一回复入口，不做多角色轮流发言界面。

#### 验收标准
- 能根据问题意图按需调用多个内部角色。
- 输出保持一个统一回复。
- 可通过调试字段看到内部角色调用轨迹。

### 7B 结构化沉淀层（进行中）

#### 目标
- 在 7A 稳定后再考虑更重能力。

#### 具体任务（当前先做最小结构化沉淀层）
1. 定义 builder 资产最小 schema（character_card / relationship_card / event_card / open_question / foreshadowing_item / gameplay_hook）。
2. 把 builder 结果落盘到本地 `data/workbench/draft/*` 目录（JSON）。
3. 资产包含最小元数据（source_query / reference_sources / generated_at）。
4. 增加最小测试与示例命令，确保可重复验证。

#### 暂时不做什么
- 不引入复杂多 agent 框架。
- 不在当前阶段做前台角色群聊 UI。
- 不接数据库，不实现完整 GraphRAG。

### 7C 审阅与发布流程（当前子阶段）

#### 目标
- 让 draft 资产具备最小人工审阅与发布闭环。

#### 具体任务
1. 建立资产状态模型：draft / approved / rejected / published。
2. 提供最小审阅命令：list draft / approve / reject / review。
3. 提供最小发布命令：仅允许 approved 资产发布到 `data/workbench/published/*`。
4. 保留可追踪元数据（source_query / reference_sources / reviewed_at / published_at）。
5. 为未来 canon/registry 对接保留字段与接口，不直接覆盖原始 canon。

#### 验收标准
- draft 资产可枚举
- 状态可流转到 approved/rejected
- 未批准资产不能发布
- 已批准资产可发布到正确目录

### 7D 已发布资产回流到系统上下文（当前子阶段）

#### 目标
- 让 `published` 资产真实影响运行时行为，而不只是静态文件。

#### 具体任务
1. 增加 published asset loader 与运行时 context 组装。
2. 至少接入 orchestrator / critic / systems_designer / builder。
3. 在 graph 检索中按需补充 published 引用信息。
4. 明确优先级：published > draft（draft 不自动提升）。
5. 保持轻量可解释性：默认轻提示，evidence 模式可看更多引用。

#### 验收标准
- 能加载 published 资产
- 至少一个模块行为受 published 资产影响
- 未发布资产不会被当成高优先级事实
- 有最小测试覆盖与示例查询

## 阶段 8：真实项目接入（增量）

### 8A 真实项目接入与导入管线（当前子阶段）

#### 目标
- 支持 `projects/<project_id>/` 真实资料目录，而不只 sample data。

#### 具体任务
1. 定义项目目录规范：`canon/draft/reference/workbench`。
2. 提供最小批量导入脚本（txt/md 优先）。
3. 约定导入 metadata（project_id/layer/doc_type/chapter/scene/characters/timeline_hint）。
4. 增加导入后检查（空文档/重复/长度异常/layer 缺失/最小角色冲突提示）。
5. 让 text/graph/orchestrator 至少可按 `project_id` 跑通。

#### 验收标准
- 有可执行导入命令
- 有导入 manifest
- 有最小检查结果
- 至少一个检索路径确认走项目目录

### 8B 真实项目质量校准（当前子阶段）

#### 目标
- 基于真实项目资料给出“可执行的结构性检查结果”。

#### 具体任务
1. 增加项目级质量检查模块（按 project_id 运行）。
2. 至少覆盖 6 类最小问题：关系冲突/时间线知情/伏笔回收/阵营链条/draft-canon 冲突/低置信提示。
3. 输出结构化 issue（含 confidence/reason/related_sources）。
4. 与现有 text/graph/published 语义保持兼容，不假装确定。

#### 验收标准
- 有脚本入口可运行
- 输出 issue 列表结构稳定
- 有最小测试覆盖核心类型

#### 8B.1 调优回合（误报降低）
- 目标：在不扩模块的前提下，降低误报并提升可解释性。
- 最小策略：
  - 低置信度阈值过滤
  - doc_type / 短文本过滤
  - 关系冲突与时间线风险的触发条件收紧
  - 伏笔未回收增加“关键词链接+已发布事件抑制”规则
  - reason/sources/entities/followup 信息增强

### 8C 项目工作台入口（当前子阶段）

#### 目标
- 将 chat/check/build/review 汇总为项目级单入口工作流。

#### 具体任务
1. 提供统一入口脚本，支持项目绑定与动作切换。
2. 至少覆盖 4 类动作：chat/check/build/review。
3. 输出结构统一，减少跨模块风格割裂。
4. 提供示例命令与最小测试，验证日常工作流可用。

#### 验收标准
- 可通过单入口完成四类动作
- project_id 可绑定并复用
- 输出 JSON 结构稳定

---

## 里程碑推进规则（执行约束）

1. **先完成当前阶段的验收，再进入下一阶段**。
2. 每阶段结束必须更新：
   - `README.md`（状态）
   - `docs/architecture.md`（职责变化）
   - 本文件（阶段状态）
3. 若需求模糊，先补文档/TODO，不直接硬写复杂实现。

---

## 当前状态建议标记（可选）

- 阶段 1：已完成
- 阶段 2：已完成
- 阶段 3：已完成
- 阶段 4：已完成
- 阶段 5：已完成
- 阶段 6：已完成
- 阶段 7A：进行中
- 阶段 7B：进行中（最小结构化沉淀层）
- 阶段 7C：进行中（最小审阅与发布流程）
- 阶段 7D：进行中（published 资产回流上下文）
- 阶段 8A：进行中（真实项目导入与 project_id 接入）
- 阶段 8B：进行中（真实项目质量校准）
- 阶段 8C：进行中（项目工作台统一入口）
- 阶段 8D：进行中（项目文件夹直导）

### 8D 项目文件夹直导（当前子阶段）

#### 目标
- 面向无基础用户提供“项目目录 + 一条命令”导入模式。

#### 具体任务
1. 支持 `incoming/canon/draft/reference/.workbench` 目录约定并自动补齐。
2. 自动扫描 txt/md，跳过系统目录（`.workbench/published/cache/logs` 等）。
3. 对 `incoming` 做最小可解释自动分类（canon/draft/reference）。
4. 自动执行分层切分并输出 `.workbench/chunks/chunks.jsonl`。
5. 生成最小工作输出（summaries/graph seed/import report）。
6. 至少一个现有模块可直接基于 `project_root` 工作。

#### 验收标准
- 用户不需要手动理解 chunk 参数
- 系统输出与用户原始文档分区清楚
- 导入报告字段稳定且可读
- 有最小测试覆盖扫描/忽略/分类/切分/报告
