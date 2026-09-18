from typing import Optional

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="用户提问")


class StartSessionResponse(BaseModel):
    session_id: str
    status: str
    question: str = ""
    created_at: float = 0


class EventResponse(BaseModel):
    session_id: str
    done: bool                      # 兼容旧客户端：是否已是终态
    status: str                     # pending / running / succeeded / failed / expired
    stage: Optional[str] = None               # 当前所处阶段，前端可以做进度提示
    stage_label: Optional[str] = None
    error: Optional[str] = None               # 失败或超时的原因
    events: list = []
    next_cursor: int = 0
    final_solution: Optional[str] = None


class SessionBrief(BaseModel):
    """只问状态、不拉事件的轻量查询。"""
    session_id: str
    status: str
    stage: Optional[str] = None
    stage_label: Optional[str] = None
    question: str = ""
    created_at: float = 0
    updated_at: float = 0
    age_sec: float = 0
    event_count: int = 0
    done: bool = False
    final_solution: Optional[str] = None
    error: Optional[str] = None


class DimensionDraft(BaseModel):
    name: str
    draft: str


class PipelineResponse(BaseModel):
    question: str
    retrieval: list = []
    retrieval_source: str = ""
    retrieval_note: str = ""
    five_focus_drafts: list = []
    group_chat_round_1: list = []
    group_chat_round_2: list = []
    final_solution: str
    elapsed_ms: float = 0
    stage_timings_ms: dict = {}
