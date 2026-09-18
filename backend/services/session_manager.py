"""会话：把 pipeline 吐出的事件存下来，让前端按游标增量拉。

这一版重点是给会话补上**生命周期**。之前只有一个 done=True/False 布尔量，
而且没有任何失败路径，导致两个实际问题：

    1. pipeline 一旦抛异常，done 永远停在 False，前端就 250ms 一次轮询到天荒地老，
       用户那边表现为「一直转圈」且不报错。
    2. 会话 dict 从来不清，跑久了内存只增不减。

现在：

    pending --run--> running --ok--> succeeded
                        |            (终态)
                        +--异常--> failed
                        |
                        +--超过 SESSION_TTL_SEC 无进展--> expired
"""
import threading
import time
import uuid
from dataclasses import dataclass, field

from backend import config
from backend.logutil import get_logger
from backend.services import pipeline

log = get_logger("session")

PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
EXPIRED = "expired"
TERMINAL = (SUCCEEDED, FAILED, EXPIRED)


class SessionCapacityExceeded(RuntimeError):
    """会话数超过上限。API 层翻译成 429，让客户端等一会儿重试。"""


@dataclass
class SessionState:
    session_id: str
    question: str
    status: str = PENDING
    stage: str = None
    error: str = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: list = field(default_factory=list)
    final_solution: str = ""

    @property
    def done(self) -> bool:
        """保留旧语义：是否已经是终态。"""
        return self.status in TERMINAL


class SessionStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: dict = {}

    # ---- 生命周期 ----
    def create(self, question: str) -> SessionState:
        """建会话。先清过期，再检查容量，最后落一个 pending 状态。"""
        with self._lock:
            self._sweep_locked()

            if len(self._sessions) >= config.SESSION_MAX:
                raise SessionCapacityExceeded(f"会话总数已达上限 {config.SESSION_MAX}")
            running = sum(1 for s in self._sessions.values() if s.status == RUNNING)
            if running >= config.SESSION_MAX_RUNNING:
                raise SessionCapacityExceeded(f"并发会话已达上限 {config.SESSION_MAX_RUNNING}")

            session = SessionState(session_id=uuid.uuid4().hex, question=question)
            self._sessions[session.session_id] = session
            total = len(self._sessions)

        log.info(f"会话创建 sid={session.session_id} 问题={question[:30]!r} 当前总数={total}/{config.SESSION_MAX}")
        return session

    def get(self, session_id: str) -> SessionState:
        """取会话，顺带判定超时——这是「卡死的会话」唯一会被收敛成终态的地方。"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.status not in TERMINAL and time.time() - session.updated_at > config.SESSION_TTL_SEC:
                session.status = EXPIRED
                session.error = f"会话超过 {int(config.SESSION_TTL_SEC)} 秒无进展，已判定超时"
                log.warning(f"会话超时 sid={session_id} 停留阶段={session.stage}")
            return session

    def mark_running(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = RUNNING
                session.updated_at = time.time()

    def set_stage(self, session_id: str, stage: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.stage = stage
                session.updated_at = time.time()

    def append_event(self, session_id: str, event: dict) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.events.append(event)
                session.updated_at = time.time()

    def succeed(self, session_id: str, final_solution: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = SUCCEEDED
                session.final_solution = final_solution
                session.updated_at = time.time()

    def fail(self, session_id: str, error: str) -> None:
        """把失败固化下来。没有这一步，前端永远等不到 done=True。"""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.status = FAILED
                session.error = error
                session.updated_at = time.time()

    # ---- 维护 ----
    def sweep_expired(self) -> int:
        with self._lock:
            return self._sweep_locked()

    def _sweep_locked(self) -> int:
        now = time.time()
        expired_ids = [
            sid
            for sid, s in self._sessions.items()
            if s.status not in TERMINAL and now - s.updated_at > config.SESSION_TTL_SEC
        ]
        for sid in expired_ids:
            del self._sessions[sid]
        if expired_ids:
            log.info(f"清理过期会话 {len(expired_ids)} 个")
        return len(expired_ids)

    def stats(self) -> dict:
        with self._lock:
            by_status: dict = {}
            for s in self._sessions.values():
                by_status[s.status] = by_status.get(s.status, 0) + 1
            oldest = min((s.created_at for s in self._sessions.values()), default=None)
            oldest_age = round(time.time() - oldest, 1) if oldest else 0.0
            return {
                "total": len(self._sessions),
                "by_status": by_status,
                "max": config.SESSION_MAX,
                "max_running": config.SESSION_MAX_RUNNING,
                "running": by_status.get(RUNNING, 0),
                "oldest_age_sec": oldest_age,
            }

    def clear(self) -> None:
        """测试用：清空所有会话。"""
        with self._lock:
            self._sessions.clear()


store = SessionStore()


def run_session_pipeline(session_id: str, question: str) -> None:
    """后台线程入口。任何异常都必须收敛成 failed，否则前端会一直轮询。"""
    started = time.perf_counter()
    store.mark_running(session_id)
    try:

        def emit(event: dict) -> None:
            store.append_event(session_id, event)
            if event.get("stage"):
                store.set_stage(session_id, event["stage"])

        result = pipeline.run_pipeline(question, emit)
        store.succeed(session_id, result.final_solution)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        log.info(f"会话成功 sid={session_id} 事件={result.event_count} 耗时={elapsed_ms}ms 检索来源={result.retrieval_source}")
    except Exception as exc:
        store.fail(session_id, f"{type(exc).__name__}: {exc}")
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        log.exception(f"会话失败 sid={session_id} 耗时={elapsed_ms}ms 原因={exc}")
