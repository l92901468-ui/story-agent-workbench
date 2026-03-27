# story-agent-workbench

一个面向**长篇游戏剧本 / 叙事资料**的通用 AI 工作台（Story Agent Workbench）。

> 目标不是做“只服务单个剧本”的一次性小工具，而是逐步沉淀一个可长期维护、可扩展的叙事创作底盘。

## 这个项目是什么

当叙事资料增长到几十万字、分散在多个文档时，创作者面对的不只是“改一段文字”，还包括：

- 跨文档的人物关系变化是否自洽
- 阵营链条是否断裂
- 时间线是否冲突
- 伏笔是否回收
- 设定之间是否互相打架

本项目要解决的，就是“**局部可检索 + 全局可推理**”这两个层面的问题。

## 核心能力（分层）

1. **普通 RAG（文本检索）**
   - 用于检索原文、草稿、设定、场景片段
   - 适合局部问题：找原句、改段落、找相关 scene

2. **GraphRAG（图谱检索 / 关系推理）**
   - 用于处理跨文档关系：人物、阵营、事件、时间线、伏笔
   - 适合全局问题：关系演化、冲突排查、回收缺口

3. **主代理 / 路由器**
   - 判断用户问题更适合文本检索还是图谱检索
   - 当前先做简单路由；后续再考虑多 agent 协调

4. **聊天式工作台（未来）**
   - 最终形态是创作对话界面
   - 当前阶段不追求 UI，先打通最小可运行闭环

## 当前阶段（MVP Skeleton）

当前优先级：

1. 结构清晰
2. 最小闭环可验证
3. 文档先行、意图先行
4. 避免过度设计

你会在文档里看到“先定义接口与边界，再逐步实现能力”的节奏。

## 数据分层观念

- **canon**：已确认、当前生效的正式内容
- **draft**：正在修改、尚未确认的草稿内容
- **reference**：参考资料、灵感材料、外部模板
- **structured registry**：结构化表（角色、地点、阵营、时间线锚点、别名等）

这套分层会直接影响检索优先级、回答可信度标注、以及后续冲突检测策略。

## 文档导航

- `PROJECT_SPEC.md`：项目愿景、问题定义、边界与路线图（核心）
- `docs/architecture.md`：模块职责与最小闭环架构
- `docs/roadmap.md`：分阶段实现顺序与验收标准
- `AGENTS.md`：协作者 / Codex 在本仓库工作的规则

## 状态

- 项目处于早期原型阶段（文档和骨架优先，当前重点见 `docs/roadmap.md`）
- 不引入复杂数据库、不做花哨前端、不做生产化优化
- 以 Python first、低依赖、可读性优先推进

## 阶段 2：最小文本接入闭环（手动验证）

当前仓库已提供最小 loader/chunker 骨架（`src/story_agent_workbench/ingest/`），用于读取 `data/samples/` 下的 `.md/.txt` 并输出 chunk 预览。

### 输入目录

- 默认目录：`data/samples/`
- 当前示例：
  - `data/samples/canon/chapter_01.md`
  - `data/samples/draft/scene_notes.txt`

`layer` 会根据路径自动推断（`canon` / `draft` / `reference`，否则为 `unknown`）。

### 运行方式

```bash
python scripts/stage2_ingest_demo.py
```

可选参数：

```bash
python scripts/stage2_ingest_demo.py --root data/samples --chunk-size 200 --overlap 20 --preview 5
```

### 你会看到什么

- 读了几个文件（documents）
- 总字符数（chars）与 layer 分布
- 生成了几个 chunk（chunks）
- chunk 预览（包含 `chunk_id/source/layer/text`）

## 阶段 3：最小普通 RAG（文本检索闭环）

在阶段 2 的 loader/chunker 基础上，当前已提供最小文本检索能力：

- 查询入口：`PYTHONPATH=src python -m story_agent_workbench "你的问题"`
- 检索模块：`src/story_agent_workbench/retrieval/text_retriever.py`
- 路由：当前为最小路由，默认走文本检索路径

### 运行方式

```bash
PYTHONPATH=src python -m story_agent_workbench "灰塔 线索"
```

可选参数：

```bash
PYTHONPATH=src python -m story_agent_workbench "罗安 冲突" --top-k 2 --data-root data/samples --chunk-size 300 --overlap 40
```

如果你想看完整结构化输出（包含 evidence/results/stats）：

```bash
PYTHONPATH=src python -m story_agent_workbench "罗安 冲突" --json
```

### 当前最小检索规则（故意保持简单）

- 基于 query 和 chunk 文本的关键词匹配做打分
- 不使用外部 embedding API
- 不引入数据库
- 不使用复杂 BM25 库或重排模型

### 验收要点

输出中应看到：
- route（当前为 `text_retrieval`）
- top_k 结果
- 每条结果包含：`source/chunk_id/layer/text/score`
- evidence（来源片段索引），便于人工核对

## 阶段 3.5：聊天回复层（最小版）

当前新增一个聊天式主回复器：

- 默认是自然聊天回复（`--mode chat`）
- 在需要时自动调用文本检索（例如问题里出现“证据/出处/冲突”等关键词）
- 证据默认不铺满屏；可用 `--show-evidence` 显示

### 回复模式

- `chat`：轻松聊剧情（默认）
- `feedback`：给可执行建议
- `critic`：挑潜在冲突
- `evidence`：只看证据

### 运行示例

```bash
PYTHONPATH=src python -m story_agent_workbench "这段冲突节奏是否太快？" --mode chat
PYTHONPATH=src python -m story_agent_workbench "给我改写建议" --mode feedback --show-evidence
PYTHONPATH=src python -m story_agent_workbench "这里哪里可能前后矛盾？" --mode critic --show-evidence
PYTHONPATH=src python -m story_agent_workbench "灰塔 线索" --mode evidence --top-k 2
```

如果想看结构化输出：

```bash
PYTHONPATH=src python -m story_agent_workbench "灰塔 线索" --mode evidence --json
```

> 说明：LLM 调用是可选能力。若环境中没有配置 `API_KEY`（或 `OPENAI_API_KEY`，或没有 openai 包），会自动回退到本地规则回复。


## 阶段 3.6：聊天层收尾与体验稳定

本阶段重点是把聊天体验稳定下来（不进入阶段 4）。

- 统一入口：仅保留 `src/story_agent_workbench/` 主包
- 推荐运行：`PYTHONPATH=src python -m story_agent_workbench "你的问题"`
- 默认体验：`mode=chat` 且默认不展示 evidence
- 证据展示条件：`mode=evidence` 或显式加 `--show-evidence`
- 最小会话记忆：默认记住最近 3 轮（本地文件）

### 会话记忆示例

```bash
PYTHONPATH=src python -m story_agent_workbench "先聊人物冲突" --session-id demo
PYTHONPATH=src python -m story_agent_workbench "再给我两个改写建议" --mode feedback --session-id demo
```

上面第二条会读取同一个 `session-id` 的最近几轮上下文。

### 四种模式职责（推荐）

- `chat`：轻松聊剧情方向（默认模式）
- `feedback`：给可执行修改建议
- `critic`：主动挑潜在冲突/不一致
- `evidence`：只看证据与来源片段

## 阶段 4：LLM 辅助的最小图层（Graph Registry + Retriever）

> 注意：这不是完整 GraphRAG，仅是最小可用图层。

当前支持的结构化 schema：

- Character
- Faction
- Location
- Event
- TimelineAnchor
- Relationship
- Alias

### 1) 从 canon 抽取结构化信息

先运行抽取脚本（默认优先尝试 LLM，失败自动回退规则抽取）：

```bash
PYTHONPATH=src python scripts/stage4_extract_registry.py --data-root data/samples --output data/extracted/registry.json
```

如需强制不使用 LLM：

```bash
PYTHONPATH=src python scripts/stage4_extract_registry.py --no-llm
```

### 2) 用聊天层触发 graph 路径

全局关系问题会优先走图路径（并可结合文本证据）：

```bash
PYTHONPATH=src python -m story_agent_workbench "艾琳和灰塔阵营有什么关系？" --mode evidence
PYTHONPATH=src python -m story_agent_workbench "灰塔阵营相关的关键人物和事件有哪些？" --mode critic --show-evidence
```

### 3) 最小能力边界

当前最小 graph retriever 能回答：

- 两个实体之间有什么关系
- 某角色关联哪些人物/阵营/事件
- 某阵营相关的关键人物和事件

输出会包含图证据来源（source/evidence），便于人工核查。

## 阶段 5：路由与回复策略层

这一阶段不只是“路由配置化”，而是把以下行为统一到策略层：

- 路由策略（text / graph）
- 回复模式策略（chat / feedback / critic / evidence）
- evidence 展示策略（full vs light）
- 弱命中回退策略（graph→text，双弱时不确定提示）

### 策略配置文件

- 默认路径：`config/strategy.json`
- 可调项示例：
  - `route_graph_keywords` / `route_text_keywords`
  - `route_graph_threshold` / `route_text_threshold`
  - `mode_keywords`（自动模式切换触发词）
  - `show_full_evidence_modes`
  - `graph_conf_threshold` / `text_conf_threshold` / `low_confidence_threshold`

### 推荐验证命令

```bash
# 1) 默认 chat，查看策略层输出（含 route confidence）
PYTHONPATH=src python -m story_agent_workbench "这段关系线怎么理顺？"

# 2) 自动切换到 evidence（关键词触发）
PYTHONPATH=src python -m story_agent_workbench "给我这段的证据出处"

# 3) graph 弱命中时，观察回退提示
PYTHONPATH=src python -m story_agent_workbench "某个不存在实体的关系" --mode critic

# 4) 非 evidence 模式，显式打开完整证据
PYTHONPATH=src python -m story_agent_workbench "灰塔阵营相关人物" --mode critic --show-evidence
```

## 阶段 6：测试与样例完善（可重复验证）

本阶段目标：把“能跑”升级为“可重复验证”。

### 自动化测试（unittest）

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

当前最小测试覆盖：
- ingest loader
- chunker
- text retriever
- graph retriever
- router / strategy
- fallback 行为
- registry extraction

### 固定示例查询集

- 路径：`examples/query_set.json`
- 覆盖：chat / feedback / critic / evidence / text retrieval / graph retrieval / weak hit fallback

### 手动验收清单

- 路径：`docs/manual_checklist.md`
- 包含：命令、预期现象、通过标准

## 阶段 7A：隐藏式多 agent 编排（无前台群聊 UI）

本阶段目标：
- 前台仍是一个统一聊天入口
- 后台按需调用多个内部角色
- 不让多个角色在前台轮流发言

### 内部角色

- `orchestrator`：统一调度
- `story_buddy`：默认陪聊剧情（LLM 优先润色）
- `critic`：按需做一致性/冲突检查（LLM 优先）
- `systems_designer`：问题偏玩法结构时给设计视角（LLM 优先）
- `builder`：按需沉淀结构化条目（角色卡/关系卡/未决问题，LLM 优先补 summary）

### 使用方式（外部入口不变）

```bash
PYTHONPATH=src python -m story_agent_workbench "我想先把这一章情绪线顺一顺"
```

你可以通过输出中的 `agents_called` 查看后台本轮调用了哪些内部角色。

### 示例问题（体现不同角色）

查看：`examples/orchestrator_queries.json`

```bash
cat examples/orchestrator_queries.json
```

## 阶段 7B：结构化沉淀层（builder draft assets）

本阶段目标：让 builder 不只“提示可沉淀”，而是把本轮对话/分析结果真正落盘为可复用资产。

### 当前支持的沉淀类型（最小 schema）

- `character_card`
- `relationship_card`
- `event_card`
- `open_question`
- `foreshadowing_item`
- `gameplay_hook`

每条资产默认包含：
- `source_query`
- `reference_sources`
- `generated_at`
- `generation_tag`

### 默认保存位置（draft，不覆盖 canon）

默认根目录：`data/workbench/draft/`

- `data/workbench/draft/characters/`
- `data/workbench/draft/relationships/`
- `data/workbench/draft/events/`
- `data/workbench/draft/open_questions/`
- `data/workbench/draft/foreshadowing/`
- `data/workbench/draft/gameplay_hooks/`

### 使用方式（外部入口不变）

```bash
PYTHONPATH=src python -m story_agent_workbench "请把艾琳与灰塔阵营关系整理成条目" --mode evidence
PYTHONPATH=src python -m story_agent_workbench "这段伏笔如何回收？请沉淀条目" --mode evidence
PYTHONPATH=src python -m story_agent_workbench "如果要做可玩任务结构，请整理 gameplay hook" --mode evidence
```

可查看 builder 示例问题：

```bash
cat examples/builder_queries.json
```
