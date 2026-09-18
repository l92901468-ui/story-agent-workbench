# 研学协同引擎（单 LLM 伪多角色）

用户提一个问题，后端先检索火山方舟知识库，再让「五维草案 → 九个维度角色 → 总控二次调和」
这条链路跑一遍，产出一份综合执行方案。前端按游标轮询事件，能看到协同过程逐条流出。

这一版主要做了两件事：**把散在两处的流程收敛成一条**，以及**补上几个必要的工程接口**。

---

## 一、流程（改完之后只有这一条）

```
POST /api/session/start           POST /api/pipeline
        │                                 │
        │  起后台线程                      │  同步执行
        └──────────────┬──────────────────┘
                       ↓
        backend/services/pipeline.py   ← 流程的唯一定义
                       │
   ┌───────────────────┼───────────────────────────────┐
   ↓                   ↓                               ↓
retrieve            draft                          discuss
检索知识库        生成五维草案                   第一轮群组沟通
   │                   │                               │
   │                   │                          reconcile
   │                   │                          二次调和
   │                   │                               │
   └───────────────────┴─────────────────────────→ finalize
                                                   产出综合方案
```

**改之前流程被写了两遍**：一份在 `backend/app.py` 的 `run_pipeline` 里，
另一份在 `backend/services/session_manager.py` 的 `run_session_pipeline` 里。
两边大体相同但细节会漂，加一个阶段要改两个地方，测试还得分别 patch
两个不同模块命名空间。现在都收敛到 `services/pipeline.py`，两个调用方共用。

流程对外的接口只有一个：

```python
events, result = pipeline.collect_events(question)      # 同步：攒起来一次性返回
result = pipeline.run_pipeline(question, emit)          # 异步：每产出一件事就交给 emit
```

每个阶段吐两类事件：

| 事件 | 说明 |
|---|---|
| `{"type":"stage", stage, status:"start"/"end", elapsed_ms}` | 阶段边界，前端拿来做进度提示 |
| `{"type":"retrieval"\|"five_focus_drafts"\|"chat"\|"final_solution", stage, payload}` | 实际内容 |

业务事件都带了 `stage` 字段，并额外携带 `seq` 和 `ts`，方便排序和排查。
`retrieval` 事件额外带 `meta`，里面是 `source`（走的火山还是本地模拟）、
`count`、`elapsed_ms`、`note`、`error`。

## 二、会话生命周期

改之前只有一个 `done=True/False`，而且**没有任何失败路径**——pipeline 一旦抛异常，
`done` 永远停在 False，前端就 250ms 一次轮询到天荒地老，用户看到的是一直转圈且不报错。
会话 dict 也从来不清，跑久了内存只增不减。

现在：

```
pending --起线程--> running --正常跑完--> succeeded
                       │
                       ├── 抛出异常 ──→ failed
                       │
                       └── 超过 SESSION_TTL_SEC 无进展 ──→ expired

succeeded / failed / expired 均为终态
```

配套的两个保护：

- **TTL 清理**：超过 `SESSION_TTL_SEC`（默认 30 分钟）没有新事件的会话，
  取用时会被判为 `expired`，后台 `sweep_expired()` 也会把它删掉
- **容量上限**：总会话数超过 `SESSION_MAX`、或并发运行数超过 `SESSION_MAX_RUNNING`，
  建会话会返回 **429**，而不是无限起线程把机器拖垮

## 三、目录

| 文件 | 职责 |
|---|---|
| `backend/config.py` | 所有环境变量集中在这里读一次，别处不再散落 `os.getenv` |
| `backend/logutil.py` | 结构化日志，控制台 + `logs/<logger>.log` 双写并按大小轮转 |
| `backend/services/pipeline.py` | **流程的唯一定义**，五个阶段 + emit 回调 |
| `backend/services/orchestrator.py` | 话术生成，纯逻辑，不做 IO、不 sleep |
| `backend/services/knowledge_base.py` | 检索层。`retrieve()` 是策略层，`search_knowledge_volc()` 是传输层 |
| `backend/services/session_manager.py` | 会话存储 + 生命周期 + TTL + 容量 |
| `backend/app.py` | HTTP 接口层，只做校验、调用、翻译状态码 |

## 四、工程接口

| 接口 | 说明 |
|---|---|
| `GET /api/health` | 不再是写死的 `{"status":"ok"}`。返回 uptime、**实际生效的配置**（尤其是检索到底走的火山还是模拟）、会话水位 |
| `GET /api/session/{id}` | 只查状态不拉事件。想知道「还要不要继续轮询」时用这个，比拉一堆事件便宜 |
| `GET /api/session/{id}/events?cursor=N` | 按游标增量拉事件，返回里带上 `status` / `stage` / `stage_label` / `error` |
| `POST /api/session/start` | 容量超限返回 **429** |
| `X-Request-Id` | 每个请求一个追踪 id，中间件自动生成并写入响应头，访问日志里带耗时 |

日志统一出口在 `logs/`，按模块拆成 `api.log` / `pipeline.log` / `session.log` /
`knowledge_base.log`。流程每进出一个阶段都会记一行带耗时：

```
2026-09-14 18:10:59 INFO  [pipeline] 阶段开始 draft(生成五维草案)
2026-09-14 18:11:00 INFO  [pipeline] 阶段结束 draft 耗时=300.2ms
2026-09-14 18:11:01 INFO  [session]  会话成功 sid=092041... 事件=33 耗时=1305.7ms 检索来源=mock
```

## 五、顺手修掉的两个坑

1. **requirements.txt 依赖写错了**。原来只写了 `volcengine-python-sdk==4.0.19`，
   但那个包提供的是 `volcenginesdk*` 各业务子包，**不含**代码实际用到的
   `volcengine.Credentials` / `auth.SignerV4` / `base.Request`，装完依然 ImportError。
   真正需要的是基础包 `volcengine`。
2. **volcengine 不再是硬依赖**。原来在 `knowledge_base.py` 顶层 import，跑纯 mock 的单元测试
   也必须装 SDK，装不上连 pytest 都起不来。现在改成惰性导入，并且**连请求对象本身都不依赖它**：
   构造请求时优先用官方 `Request`，导入失败就退回内置的 `_SimpleRequest` 替身；
   只有真正要用 AK/SK 签名时才必须有这个包，缺了会给出「pip install volcengine」的明确提示。
   已验证：**装了 SDK 和完全不装 SDK 两种环境下，23 个用例都是全绿的。**

另外检索失败以前被吞成空 list，「没检索到」和「调用炸了」完全分不清。
现在 `search_knowledge_volc` 失败会抛 `RetrievalError`，`retrieve` 降级到本地模拟
但把原因记在 `RetrievalResult.error` 和日志里。

## 六、跑起来

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload --port 8000
```

访问 `http://127.0.0.1:8000/`。**不配任何密钥也能直接跑**，会自动落到本地模拟检索。
同理，不装 `volcengine` 也能跑——只有真要调火山时才需要它。

```bash
pytest -q          # 23 个用例，约 0.8 秒
```

## 七、环境变量

火山方舟（三个都配齐才走真实检索，缺任意一个自动回退本地模拟）：

```bash
export VOLC_AK="your_ak"
export VOLC_SK="your_sk"
export VOLC_ACCOUNT_ID="your_account_id"
export VOLC_KB_DOMAIN="api-knowledgebase.mlp.cn-beijing.volces.com"
export VOLC_PROJECT_NAME="default"
export VOLC_COLLECTION_NAME="file"
```

工程相关（都有默认值，按需覆盖）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `RETRIEVAL_MOCK` | false | 强制走本地模拟，完全不碰火山 |
| `RETRIEVAL_TOP_K` | 5 | 实际使用的检索条数 |
| `RETRIEVAL_TIMEOUT_SEC` | 12 | 调火山的超时 |
| `SESSION_TTL_SEC` | 1800 | 会话超时判定 |
| `SESSION_MAX` | 500 | 会话总数上限 |
| `SESSION_MAX_RUNNING` | 16 | 并发会话上限 |
| `STREAM_SLEEP_SEC` | 0.05 | 每条群聊消息之间的间隔，纯粹为了流式观感；压测设 0 |
| `DRAFT_SLEEP_SEC` | 0.3 | 草案阶段的人为停顿 |
| `LOG_DIR` / `LOG_LEVEL` | logs / INFO | 日志位置与级别 |

> 请勿将真实密钥提交到代码仓库。
