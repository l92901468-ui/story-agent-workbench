# Architecture (MVP Skeleton)

本文档解释当前骨架的职责边界与最小闭环，重点回答：

- 这个项目现在处于什么阶段
- 每个模块负责什么
- 为什么先这样设计
- 当前做什么 / 暂时不做什么

## 1. 当前架构目标

当前目标不是“功能齐全”，而是：

1. 用最小模块把主流程串起来
2. 把未来扩展点先留清楚
3. 保持新手可读、可维护

即：先把“能跑通的骨架”搭起来，再逐步强化检索与推理能力。

---

## 1.5 包结构与入口（阶段 3.6）

- 仅保留一套主包结构：`src/story_agent_workbench/`
- 推荐入口：`PYTHONPATH=src python -m story_agent_workbench "你的问题"`
- 避免同时维护重复包路径，减少协作者理解成本。


---

## 2. 主流程（概念）

用户问题 → `main.py` 入口 → `agent_router.py` 路由决策 →
- 文本问题：`text_retriever.py`
- 全局关系问题：`graph_retriever.py`

然后将结果统一返回给调用方（当前可先用简化返回结构）。

---

## 3. 模块职责

### 3.1 CLI 入口
- 路径：`src/story_agent_workbench/main.py`
- 职责：
  - 接收用户输入
  - 调用路由器
  - 输出统一结果

### 3.2 主路由器
- 路径：`src/story_agent_workbench/router/agent_router.py`
- 职责：
  - 判断问题类型（局部文本 vs 全局关系）
  - 分发到对应检索模块
- 当前策略：
  - 规则优先（简单、可解释）
  - 输出 `route/reason/confidence`

### 3.2.2 路由与回复策略层（阶段 5）
- 配置路径：`config/strategy.json`
- 代码路径：`src/story_agent_workbench/strategy/config.py`
- 覆盖内容：
  - 路由触发关键词与阈值（text vs graph）
  - mode 自动切换策略（默认 chat）
  - evidence 展示策略（full vs light citation）
  - 弱命中回退策略（graph→text，双弱时不确定提示）

### 3.2.5 聊天回复层（阶段 5 策略接入）
- 路径：`src/story_agent_workbench/chat/reply_layer.py`
- 职责：
  - 提供聊天式主回复（chat/feedback/critic/evidence）
  - 按需调用文本检索，不默认铺满 evidence
  - 支持最小会话记忆（最近几轮，本地文件）
  - 在可用时可选调用 LLM，不可用时回退本地规则回复
- 默认体验：
  - 默认 `mode=chat`
  - 默认不展示 evidence
  - 仅 `mode=evidence` 或 `--show-evidence` 显示证据


### 3.2.8 隐藏式多 agent 编排（阶段 7A）
- 路径：`src/story_agent_workbench/orchestrator/orchestrator.py`
- 内部角色：story_buddy / critic / systems_designer / builder
- 外部行为：
  - 前台仍是单一回复
  - 后台按需调用多角色
  - 可通过 `agents_called` 观察本轮编排
- 角色生成策略：
  - 内部角色默认优先调用 LLM（支持 `API_KEY` 或 `OPENAI_API_KEY`）
  - 若 LLM 不可用或失败，自动回退本地规则模板

### 3.2.9 结构化沉淀层（阶段 7B）
- 路径：
  - `src/story_agent_workbench/orchestrator/assets.py`
  - `src/story_agent_workbench/orchestrator/roles.py`（builder）
- 职责：
  - 定义 builder 资产最小 schema
  - 将本轮沉淀条目写入本地 draft 资产目录（JSON）
- 当前支持类型：
  - character_card / relationship_card / event_card / open_question / foreshadowing_item / gameplay_hook
- 默认保存根目录：
  - `data/workbench/draft/`
- 约束：
  - 仅写 draft 资产，不覆盖 canon
  - 不接数据库，不做 UI

### 3.2.10 审阅与发布流程（阶段 7C）
- 路径：
  - `src/story_agent_workbench/orchestrator/assets.py`
  - `scripts/stage7c_asset_review.py`
- 职责：
  - 对 draft 资产执行审阅动作（approve/reject）
  - 仅允许 approved 资产发布到 `data/workbench/published/*`
  - 保留审阅和发布时间信息，保证可追踪
- 状态模型：
  - draft / approved / rejected / published
- 对接原则：
  - 当前不直接修改 canon 文本
  - published 资产保留 `asset_type` 与 `metadata.target_integration`，为未来 canon/registry 映射留接口

### 3.2.11 已发布资产回流（阶段 7D）
- 共享模块路径：`src/story_agent_workbench/core/published_assets.py`
- 职责：
  - 加载 `data/workbench/published/*` 资产
  - 构建运行时资产上下文
  - 按 query 做轻量相关性匹配
- 当前接入：
  - orchestrator / critic / systems_designer / builder
  - graph retriever（补充 published 引用）
- 优先级：
  - published 是高优先级工作事实层
  - draft 不自动提升
  - 不直接覆盖 canon 文本

### 3.3 文本检索模块
- 路径：`src/story_agent_workbench/retrieval/text_retriever.py`
- 职责：
  - 面向普通 RAG 的本地文本片段检索
  - 回答局部问题
- 当前状态：
  - 已实现最小关键词打分检索（阶段 3）
  - 已支持本地持久化索引（JSON）以跨运行复用 chunk
  - 可接入临时测试文件（`--test-file`），并在本轮直接参与检索
  - 返回结果包含 `source/chunk_id/layer/text/score` 与 evidence

### 3.4 图谱检索模块（阶段 4 最小版）
- 路径：`src/story_agent_workbench/graph/graph_retriever.py`
- 职责：
  - 基于结构化 registry 回答全局关系问题
  - 支撑人物关系、阵营链条、关键事件检索
- 当前状态：
  - 非 GraphRAG 的最小图层实现（JSON + 本地检索）
  - 支持 relationship_between / character_context / faction_context

### 3.4.5 抽取模块（LLM 辅助）
- 路径：`src/story_agent_workbench/graph/extractor.py`
- 入口脚本：`scripts/stage4_extract_registry.py`
- 输出：`data/extracted/registry.json`
- 策略：
  - 有可用 API key 时优先 LLM 抽取
  - LLM 失败时自动回退规则抽取

### 3.5 ingest 模块（阶段 2 已落地）
- `src/story_agent_workbench/ingest/`：最小文本读取与切分（loader/chunker）

### 3.5.5 真实项目导入管线（阶段 8A）
- 路径：
  - `src/story_agent_workbench/ingest/project_importer.py`
  - `scripts/stage8a_import_project.py`
- 目录规范：
  - `projects/<project_id>/canon|draft|reference|workbench`
- 职责：
  - 批量导入 txt/md
  - 生成最小 metadata（project_id/layer/doc_type/chapter/scene/characters/timeline_hint）
  - 输出导入 manifest 与质量检查告警

### 3.6 预留目录
- `src/story_agent_workbench/core/`：通用配置、类型、公共工具（后续）

### 3.7 project_id 运行时接入（阶段 8A）
- `main.py` 支持 `--project-id --projects-root`
- text retriever 可按 `project_id` 读取 `projects/<project_id>/`
- graph retriever 可按 `project_id` 读取 `projects/<project_id>/workbench/extracted/registry.json`
- orchestrator/published context 继续走项目内 `workbench/published`（若存在）

### 3.8 项目质量校准层（阶段 8B）
- 路径：
  - `src/story_agent_workbench/quality/project_quality.py`
  - `scripts/stage8b_project_quality_check.py`
- 职责：
  - 对真实项目做结构性质量检查（最小版）
  - 输出结构化问题列表（含 confidence/reason/sources）
- 当前最小检查覆盖：
  - 人物关系冲突
  - 时间线/知情时点风险
  - 伏笔未回收
  - 阵营链条缺口
  - draft vs canon 冲突
  - 低置信度声明
- 8B.1 调优要点：
  - 引入最小阈值与过滤（低置信度过滤、doc_type 过滤、短文本过滤）
  - 对关系冲突/时间线/伏笔未回收的误报做规则降噪
  - issue reason/sources/entities/followup 更具体，便于人工复核

### 3.9 项目工作台入口（阶段 8C）
- 路径：`scripts/stage8c_project_session.py`
- 统一动作：
  - `chat`
  - `check`
  - `build`
  - `review`
- 设计目标：
  - 单入口绑定 `project_id`
  - 统一 JSON 输出结构
  - 复用现有 chat/quality/builder/review 能力，降低日常使用成本

### 3.6 预留目录
- `src/story_agent_workbench/core/`：通用配置、类型、公共工具（后续）

---

## 4. 数据层语义（强约定）

检索与回答必须逐步支持以下语义分层：

- `canon`：正式成立内容
- `draft`：未确认草稿
- `reference`：参考资料
- `structured registry`：角色/地点/阵营/时间锚点/别名等结构化事实

这决定了未来的：
- 召回优先级
- 回答可信度说明
- 冲突检测的判定顺序

---

## 5. 为什么不直接上复杂方案

因为当前阶段重点是“最小可验证闭环”：

- 让入口、路由、检索边界先稳定
- 让文档能指导协作者对齐目标
- 防止项目在早期被复杂技术栈拖慢

这符合仓库的开发策略：Python first、低依赖、可读性优先。

---

## 6. 当前不做的内容

- 生产级 GraphRAG 管线
- 复杂数据库 / 分布式架构
- 完整多 agent 编排系统
- UI/前端美化

这些能力会在路线图阶段逐步引入，而不是在骨架期一次性实现。

---

## 7. 下一步建议

1. 在 `main.py` 到路由器之间约定统一请求/响应结构
2. 在 `text_retriever.py` 定义最小可演示检索流程（本地文件优先）
3. 在 `graph_retriever.py` 固化查询接口，先返回可解释占位结果
4. 在 `src/story_agent_workbench/ingest/` 继续完善输入数据格式约定（txt/md 优先）

这四步完成后，可进入“可验证最小检索闭环”阶段。


## 8. 阶段 6 验证层（测试与样例）

- 自动化测试目录：`tests/`（标准库 `unittest`）
- 示例查询集：`examples/query_set.json`
- 手动验收清单：`docs/manual_checklist.md`

验证目标：
- 关键路径可重复执行
- 失败场景可复现
- 新协作者可按文档完成最小验收

### 3.10 项目文件夹直导（阶段 8D）
- 路径：
  - `src/story_agent_workbench/ingest/folder_import.py`
  - `scripts/stage8c_folder_import.py`
- 目录语义：
  - 用户输入层：`incoming/canon/draft/reference`
  - 系统输出层：`.workbench/*`
- 职责：
  - 自动补齐缺失目录
  - 自动扫描并忽略系统目录
  - 对 `incoming` 做最小可解释分类
  - 分层切分（标题/对话块/段落优先，最后固定长度回退）
  - 写入 chunks/summaries/graph seed/import report
- 与现有模块接入：
  - `text_retriever` 优先读取 `.workbench/chunks/chunks.jsonl`
  - `graph_retriever` 可读取 `.workbench/graph/registry_seed.json`
  - `project_quality` 会复用 `.workbench/logs/import_report.json`
