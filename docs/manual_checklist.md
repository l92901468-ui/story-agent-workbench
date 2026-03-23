# Manual Checklist（阶段 6）

本清单用于把当前项目从“能跑”提升到“可重复验证”。

## 0) 前置条件

- 当前目录位于仓库根目录
- 使用 Python 3.10+
- 已有样例数据：`data/samples/`

## 1) 运行最小自动化测试

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

### 预期现象
- 所有测试通过（OK）
- 覆盖 ingest / chunker / text retriever / graph retriever / router strategy / fallback / extractor

### 通过标准
- 退出码为 0
- 输出中无 FAIL/ERROR

## 2) 验证阶段 4 抽取可复现

```bash
PYTHONPATH=src python scripts/stage4_extract_registry.py --no-llm --output data/extracted/registry.json
```

### 预期现象
- 输出各类结构计数（characters/factions/...）
- `data/extracted/registry.json` 被更新

### 通过标准
- 命令退出成功
- JSON 文件存在且可读取

## 3) 验证阶段 5 策略行为

### 3.1 默认 chat + 轻量引用
```bash
PYTHONPATH=src python -m story_agent_workbench "这段关系线怎么理顺？"
```

### 3.2 自动模式切换（chat -> feedback）
```bash
PYTHONPATH=src python -m story_agent_workbench "给我改写建议" --json
```

### 3.3 evidence 模式全量证据
```bash
PYTHONPATH=src python -m story_agent_workbench "艾琳和灰塔阵营有什么关系？" --mode evidence
```

### 3.4 弱命中 fallback
```bash
PYTHONPATH=src python -m story_agent_workbench "不存在实体和灰塔阵营有什么关系？" --mode critic
```

### 预期现象
- 输出包含 route confidence
- 输出包含 mode / mode_reason
- evidence 模式显示 full evidence
- 弱命中时有 fallback 提示（不假装确定）

### 通过标准
- 命令全部成功
- 输出行为与上述预期一致

## 4) 验证示例查询集

查看示例集：

```bash
cat examples/query_set.json
```

### 预期现象
- 包含 chat / feedback / critic / evidence / text / graph / weak_hit_fallback 七类

### 通过标准
- 每类至少 1 条示例查询

## 5) 验证阶段 7A（隐藏式多 agent 编排）

```bash
PYTHONPATH=src python -m story_agent_workbench "我想先把这一章情绪线顺一顺"
PYTHONPATH=src python -m story_agent_workbench "这里的人物动机会不会前后矛盾？" --mode critic
PYTHONPATH=src python -m story_agent_workbench "如果要做可玩任务结构，这段剧情怎么设计互动目标？"
```

### 预期现象
- 输出仍是单一统一回复
- 可看到 `agents_called`，且根据问题不同会包含不同内部角色

### 通过标准
- 不出现前台多角色轮流发言 UI
- 至少能观察到 story_buddy / critic / systems_designer 的按需调用

## 6) 验证阶段 7B（结构化沉淀层）

```bash
PYTHONPATH=src python -m story_agent_workbench "请把艾琳与灰塔阵营关系整理成条目" --mode evidence
cat examples/builder_queries.json
```

### 预期现象
- 输出中包含 `builder_entries` 与 `builder_saved_assets`
- 本地生成 draft 资产文件（JSON）

### 通过标准
- `data/workbench/draft/` 下出现以下目录之一并包含文件：
  - `characters/`
  - `relationships/`
  - `events/`
  - `open_questions/`
  - `foreshadowing/`
  - `gameplay_hooks/`
