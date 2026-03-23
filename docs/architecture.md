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
  - 暂不引入复杂多 agent 编排

### 3.2.5 聊天回复层（阶段 3.6）
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

### 3.3 文本检索模块
- 路径：`src/story_agent_workbench/retrieval/text_retriever.py`
- 职责：
  - 面向普通 RAG 的本地文本片段检索
  - 回答局部问题
- 当前状态：
  - 已实现最小关键词打分检索（阶段 3）
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
