"""整个协同流程的**唯一**定义。

之前流程被写了两遍：
    backend/app.py                  -> run_pipeline 里一串
    backend/services/session_manager.py -> run_session_pipeline 里又一串

两边逻辑大体相同但细节会漂（cli 那边改了忘了同步，异步这边漏一个事件），
加一个阶段要改两个地方。现在收敛到这里一条：

    retrieve -> draft -> discuss(第一轮) -> reconcile(第二轮) -> finalize

每个阶段吐两类事件：
    {"type": "stage", stage, status: start|end, elapsed_ms}   阶段边界，前端做进度条
    {"type": 业务事件, stage, payload}                         实际内容

调用方决定事件去哪（emit 回调）：
    会话模式 -> 写进 SessionStore，前端按游标增量拉
    同步模式 -> 收集进内存列表，一次性拼成 PipelineResponse
"""
import itertools
import time
from dataclasses import dataclass, field
from typing import Callable

from backend import config
from backend.logutil import get_logger
from backend.schemas import DimensionDraft
from backend.services import knowledge_base, orchestrator

log = get_logger("pipeline")

RETRIEVE = "retrieve"
DRAFT = "draft"
DISCUSS = "discuss"
RECONCILE = "reconcile"
FINALIZE = "finalize"

STAGES = (RETRIEVE, DRAFT, DISCUSS, RECONCILE, FINALIZE)
STAGE_LABELS = {
    RETRIEVE: "检索知识库",
    DRAFT: "生成五维草案",
    DISCUSS: "第一轮群组沟通",
    RECONCILE: "二次调和",
    FINALIZE: "产出综合方案",
}
STAGE_ORDER = {name: idx for idx, name in enumerate(STAGES)}


@dataclass
class PipelineResult:
    """一次完整跑完的产物。同步接口和会话模式共用。"""

    question: str
    retrieval: list
    retrieval_source: str
    retrieval_note: str
    five_focus_drafts: list = field(default_factory=list)
    group_chat_round_1: list = field(default_factory=list)
    group_chat_round_2: list = field(default_factory=list)
    final_solution: str = ""
    elapsed_ms: float = 0.0
    event_count: int = 0
    stage_timings_ms: dict = field(default_factory=dict)


Emitter = Callable[[dict], None]


def run_pipeline(question: str, emit: Emitter, *, round_delay: float = None, draft_delay: float = None) -> PipelineResult:
    """按阶段跑一遍完整流程，每产出一样东西就交给 emit。

    round_delay / draft_delay 默认读 config，压测或测试时传 0 关掉人为节流。
    """
    round_delay = config.STREAM_SLEEP_SEC if round_delay is None else round_delay
    draft_delay = config.DRAFT_SLEEP_SEC if draft_delay is None else draft_delay

    seq = itertools.count(1)
    timings: dict = {}
    counter = {"n": 0}

    def _emit(type_: str, **fields) -> None:
        event = {"seq": next(seq), "ts": time.time(), "type": type_}
        event.update(fields)
        counter["n"] += 1
        emit(event)

    def _enter(stage: str) -> float:
        _emit("stage", stage=stage, status="start", label=STAGE_LABELS[stage], order=STAGE_ORDER[stage])
        log.info(f"阶段开始 {stage}({STAGE_LABELS[stage]})")
        return time.perf_counter()

    def _leave(stage: str, started: float) -> None:
        timings[stage] = round((time.perf_counter() - started) * 1000, 1)
        log.info(f"阶段结束 {stage} 耗时={timings[stage]}ms")
        _emit(
            "stage",
            stage=stage,
            status="end",
            label=STAGE_LABELS[stage],
            order=STAGE_ORDER[stage],
            elapsed_ms=timings[stage],
        )

    total_started = time.perf_counter()
    log.info(f"流程启动 question={question[:40]!r} 节流 round={round_delay}s draft={draft_delay}s")

    # ---- 1. 检索 ----
    clock = _enter(RETRIEVE)
    retrieval = knowledge_base.retrieve(question)
    if retrieval.error:
        log.warning(f"检索降级 source={retrieval.source} 原因={retrieval.error}")
    _emit(
        "retrieval",
        stage=RETRIEVE,
        payload=retrieval.items,
        meta={
            "source": retrieval.source,
            "count": len(retrieval.items),
            "elapsed_ms": retrieval.elapsed_ms,
            "note": retrieval.note,
            "error": retrieval.error,
        },
    )
    _leave(RETRIEVE, clock)

    # ---- 2. 五维草案 ----
    clock = _enter(DRAFT)
    five_drafts: list = orchestrator.generate_five_focus_drafts(question, retrieval.items)
    if draft_delay:
        time.sleep(draft_delay)
    _emit("five_focus_drafts", stage=DRAFT, payload=[d.model_dump() for d in five_drafts])
    _leave(DRAFT, clock)

    # ---- 3. 第一轮群组沟通 ----
    clock = _enter(DISCUSS)
    round_1 = orchestrator.build_chat_round_1(question, five_drafts)
    for msg in round_1:
        _emit("chat", stage=DISCUSS, round=1, payload=msg)
        if round_delay:
            time.sleep(round_delay)
    _leave(DISCUSS, clock)

    # ---- 4. 二次调和 ----
    clock = _enter(RECONCILE)
    round_2, final_solution = orchestrator.build_chat_round_2(five_drafts)
    for msg in round_2:
        _emit("chat", stage=RECONCILE, round=2, payload=msg)
        if round_delay:
            time.sleep(round_delay)
    _leave(RECONCILE, clock)

    # ---- 5. 产出最终方案 ----
    clock = _enter(FINALIZE)
    _emit("final_solution", stage=FINALIZE, payload=final_solution)
    _leave(FINALIZE, clock)

    elapsed_ms = round((time.perf_counter() - total_started) * 1000, 1)
    log.info(f"流程完成 事件={counter['n']}个 总耗时={elapsed_ms}ms 阶段耗时={timings}")

    return PipelineResult(
        question=question,
        retrieval=retrieval.items,
        retrieval_source=retrieval.source,
        retrieval_note=retrieval.note,
        five_focus_drafts=five_drafts,
        group_chat_round_1=round_1,
        group_chat_round_2=round_2,
        final_solution=final_solution,
        elapsed_ms=elapsed_ms,
        event_count=counter["n"],
        stage_timings_ms=timings,
    )


def collect_events(question: str, **kwargs) -> tuple:
    """同步跑一遍，把事件全攒下来。给 /api/pipeline 用。"""
    events: list = []
    result = run_pipeline(question, events.append, **kwargs)
    return events, result
