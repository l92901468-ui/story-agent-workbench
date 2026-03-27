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

## 7) 验证阶段 7C（审阅与发布流程）

```bash
# 列出 draft 资产
PYTHONPATH=src python scripts/stage7c_asset_review.py list-draft --workbench-root data/workbench

# 批准一个资产（替换为真实路径）
PYTHONPATH=src python scripts/stage7c_asset_review.py approve --asset-path data/workbench/draft/open_questions/<your_file>.json --note "可发布"

# 发布已批准资产
PYTHONPATH=src python scripts/stage7c_asset_review.py publish --asset-path data/workbench/draft/open_questions/<your_file>.json --workbench-root data/workbench
```

### 预期现象
- `approve/reject` 会更新资产状态与审阅信息
- `publish` 仅允许 approved 资产
- 发布后资产进入 `data/workbench/published/*`

### 通过标准
- 未批准资产发布时报错
- 已批准资产能成功发布到对应类型目录

## 8) 验证阶段 7D（已发布资产回流）

```bash
cat examples/published_context_queries.json
PYTHONPATH=src python -m story_agent_workbench "参考已发布关系卡，帮我检查艾琳与灰塔阵营的冲突点。" --mode critic
```

### 预期现象
- 输出可出现轻量提示：参考了已发布资产
- 在 evidence 模式下可看到更多 published 引用

### 通过标准
- published 资产能影响至少一个模块的输出行为
- draft 资产不会自动被当成高优先级事实

## 9) 验证阶段 8A（真实项目导入与 project_id）

```bash
PYTHONPATH=src python scripts/stage8a_import_project.py --project-id demo_project --projects-root projects
PYTHONPATH=src python -m story_agent_workbench "灰塔阵营关系" --project-id demo_project --projects-root projects
```

### 预期现象
- 生成 `projects/demo_project/workbench/import_manifest.json`
- 输出导入统计与检查项
- 主入口能按 `project_id` 使用项目资料

### 通过标准
- 导入命令成功且 manifest 可读
- 检索结果来源包含 `projects/<project_id>/...` 或相对路径

## 10) 验证阶段 8B（真实项目质量校准）

```bash
cat examples/project_quality_checks.json
PYTHONPATH=src python scripts/stage8b_project_quality_check.py --project-id demo_project --projects-root projects
```

### 预期现象
- 输出 issue 列表（可为 0~N 条）
- 每条 issue 至少包含 type/summary/confidence/reason/sources

### 通过标准
- 命令成功执行
- JSON 模式下字段结构稳定（issue_type/confidence/reason/related_sources）

## 11) 验证阶段 8B.1（调优回合）

```bash
cat examples/project_quality_tuning_cases.json
PYTHONPATH=src python -m unittest tests/test_project_quality.py -v
```

### 预期现象
- 误报降低场景（如过渡词、无链接伏笔）不再触发 issue
- reason 更具体（包含来源对照或触发词）
- 低置信度/噪声场景不强报

### 通过标准
- 测试覆盖至少 2 类误报降低场景
- 至少 1 类解释性增强断言通过

## 12) 验证阶段 8C（项目工作台入口）

```bash
cat examples/project_session_commands.json
PYTHONPATH=src python scripts/stage8c_project_session.py --project-id demo_project --projects-root projects chat "先帮我顺一下这一章冲突线"
PYTHONPATH=src python scripts/stage8c_project_session.py --projects-root projects check --top 3
PYTHONPATH=src python scripts/stage8c_project_session.py --projects-root projects build "请整理这轮可沉淀条目"
PYTHONPATH=src python scripts/stage8c_project_session.py --projects-root projects review --do list --status draft
```

### 预期现象
- 四类动作都能从统一入口执行
- 后续命令可复用 session 中绑定的 project_id
- 输出均为结构化 JSON

### 通过标准
- chat/check/build/review 至少各成功执行 1 次
- build 后 review list 能看到 draft 资产

## 13) 验证阶段 8D（项目文件夹直导）

```bash
cat examples/folder_import_commands.json
PYTHONPATH=src python scripts/stage8c_folder_import.py --project-root projects/demo_project
PYTHONPATH=src python scripts/stage8c_folder_import.py --project-root projects/demo_project --json
```

### 预期现象
- 自动补齐 `incoming/canon/draft/reference/.workbench` 目录
- 自动忽略 `.workbench/` 等系统目录
- 生成 `.workbench/chunks/chunks.jsonl`
- 生成 `.workbench/logs/import_report.json`
- 报告包含扫描数、自动分类数、chunk 数、跳过项与问题项

### 通过标准
- 命令成功
- 报告可读取且字段完整
