import time

import pytest

from backend import config
from backend.services import session_manager


@pytest.fixture(autouse=True)
def isolate():
    """每个用例的默认环境：关掉人为节流、清空会话表。

    节流本来只是为了让前端看得见流式效果，测试里留着纯粹浪费时间。
    """
    originals = {"STREAM_SLEEP_SEC": config.STREAM_SLEEP_SEC, "DRAFT_SLEEP_SEC": config.DRAFT_SLEEP_SEC}
    config.STREAM_SLEEP_SEC = 0.0
    config.DRAFT_SLEEP_SEC = 0.0
    session_manager.store.clear()
    yield
    for key, value in originals.items():
        setattr(config, key, value)
    session_manager.store.clear()


@pytest.fixture
def fake_retrieval(monkeypatch):
    """把检索替换掉。

    以前测试要在两个不同的模块命名空间各 patch 一次：
    backend.app.search_knowledge_volc 和 backend.services.session_manager.search_knowledge_volc。
    流程统一到 pipeline 之后，只 patch knowledge_base.retrieve 一个点就够。
    """

    def _install(items=None, source="fake"):
        from backend.services import knowledge_base

        payload = items if items is not None else [{"title": "t1", "snippet": "s1"}]
        monkeypatch.setattr(
            knowledge_base,
            "retrieve",
            lambda question: knowledge_base.RetrievalResult(items=payload, source=source, elapsed_ms=1.0),
        )

    return _install


def wait_terminal(client, session_id, timeout=5.0):
    """轮询直到会话进入终态，返回结果 dict。超时直接抛断言错误，而不是挂在 while 里。"""
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        resp = client.get(f"/api/session/{session_id}")
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["done"]:
            return last
        time.sleep(0.02)
    raise AssertionError(f"会话未在 {timeout}s 内进入终态，最后一次状态：{last}")
