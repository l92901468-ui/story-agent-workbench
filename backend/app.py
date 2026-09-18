"""HTTP 接口层。

只做三件事：参数校验、调用 services、把结果翻译成 HTTP 语义。
业务逻辑一行都不在这里——之前 /api/pipeline 和会话模式各写了一遍流程，
加一个阶段要改两个地方，现在都收敛到 services/pipeline.py。

新增的少量工程接口：
    GET  /api/health                 带配置与会话水位，不再是写死的 {"status":"ok"}
    GET  /api/session/{id}           只查状态，不用把事件全拉回来
    X-Request-Id                     每个请求一个追踪 id，中间件自动注入并记录耗时
"""
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.logutil import get_logger
from backend.schemas import AskRequest, EventResponse, PipelineResponse, SessionBrief, StartSessionResponse
from backend.services import pipeline
from backend.services.session_manager import SessionCapacityExceeded, run_session_pipeline, store

log = get_logger("api")

STARTED_AT = time.time()

app = FastAPI(title="Pseudo Multi-Agent Study Planner", version=config.SERVICE_VERSION)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """注入 request_id 并记录一行访问日志。排查问题时按这个 id 串前后端。"""
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        log.exception(f"[{request_id}] {request.method} {request.url.path} -> 未捕获异常 {elapsed_ms}ms")
        raise
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-Id"] = request_id
    log.info(f"[{request_id}] {request.method} {request.url.path} -> {response.status_code} {elapsed_ms}ms")
    return response


@app.get("/")
def index() -> FileResponse:
    return FileResponse("frontend/index.html")


app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/api/health")
def health() -> dict:
    """健康检查。暴露配置走向和会话水位，方便一眼看出「是不是没配密钥才走的模拟」。"""
    return {
        "status": "ok",
        "uptime_sec": round(time.time() - STARTED_AT, 1),
        "config": config.summary(),
        "sessions": store.stats(),
    }


@app.post("/api/pipeline", response_model=PipelineResponse)
def run_pipeline_api(req: AskRequest) -> PipelineResponse:
    """一次性跑完并返回完整结果。调试用，和会话模式走同一份流程定义。"""
    started = time.perf_counter()
    _, result = pipeline.collect_events(req.question)

    log.info(
        f"同步流程完成 检索来源={result.retrieval_source} 事件={result.event_count} "
        f"耗时={result.elapsed_ms}ms 接口总耗时={round((time.perf_counter() - started) * 1000, 1)}ms"
    )
    return PipelineResponse(
        question=result.question,
        retrieval=result.retrieval,
        retrieval_source=result.retrieval_source,
        retrieval_note=result.retrieval_note,
        five_focus_drafts=result.five_focus_drafts,
        group_chat_round_1=result.group_chat_round_1,
        group_chat_round_2=result.group_chat_round_2,
        final_solution=result.final_solution,
        elapsed_ms=result.elapsed_ms,
        stage_timings_ms=result.stage_timings_ms,
    )


@app.post("/api/session/start", response_model=StartSessionResponse)
def start_session(req: AskRequest) -> StartSessionResponse:
    """建会话并在后台起一个线程跑流程，立刻返回 session_id。"""
    try:
        session = store.create(req.question)
    except SessionCapacityExceeded as exc:
        log.warning(f"会话创建被拒 原因={exc}")
        raise HTTPException(status_code=429, detail=str(exc))

    thread = threading.Thread(target=run_session_pipeline, args=(session.session_id, req.question), daemon=True)
    thread.start()

    return StartSessionResponse(
        session_id=session.session_id,
        status=session.status,
        question=session.question,
        created_at=session.created_at,
    )


@app.get("/api/session/{session_id}", response_model=SessionBrief)
def get_session(session_id: str) -> SessionBrief:
    """只看状态，不拉事件。前端可以先查这个判断要不要继续轮询。"""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    stage_label = pipeline.STAGE_LABELS.get(session.stage) if session.stage else None
    return SessionBrief(
        session_id=session.session_id,
        status=session.status,
        stage=session.stage,
        stage_label=stage_label,
        question=session.question,
        created_at=session.created_at,
        updated_at=session.updated_at,
        age_sec=round(time.time() - session.created_at, 1),
        event_count=len(session.events),
        done=session.done,
        final_solution=session.final_solution or None,
        error=session.error,
    )


@app.get("/api/session/{session_id}/events", response_model=EventResponse)
def get_events(session_id: str, cursor: int = 0) -> EventResponse:
    """按游标增量拉事件。比 SessionBrief 多带当前批次的事件内容。"""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    events = session.events[cursor:]
    next_cursor = cursor + len(events)
    stage_label = pipeline.STAGE_LABELS.get(session.stage) if session.stage else None

    return EventResponse(
        session_id=session_id,
        done=session.done,
        status=session.status,
        stage=session.stage,
        stage_label=stage_label,
        error=session.error,
        events=events,
        next_cursor=next_cursor,
        final_solution=session.final_solution if session.done else None,
    )
