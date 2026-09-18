"""会话生命周期用例。

覆盖的是这一版补上的能力：显式状态、超时收敛、容量上限、异常固化。
这些在改动前全是缺口——尤其是「pipeline 抛异常后没有任何失败态」，
当时客户端会永远轮询下去。
"""
import time

from fastapi.testclient import TestClient

from backend import config
from backend.app import app
from backend.services import session_manager
from tests.conftest import wait_terminal

client = TestClient(app)


def test_idle_session_expires_instead_of_hanging(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SEC", 0.05)

    session = session_manager.store.create("没人跑的问题")
    time.sleep(0.12)

    body = client.get(f"/api/session/{session.session_id}").json()
    assert body["done"] is True
    assert body["status"] == "expired"
    assert "超时" in body["error"]


def test_expired_session_stops_event_polling(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SEC", 0.05)

    session = session_manager.store.create("没人跑的问题")
    time.sleep(0.12)

    events = client.get(f"/api/session/{session.session_id}/events").json()
    assert events["done"] is True
    assert events["status"] == "expired"


def test_total_capacity_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(config, "SESSION_MAX", 1)

    session_manager.store.create("占掉唯一名额")

    resp = client.post("/api/session/start", json={"question": "第二个问题"})
    assert resp.status_code == 429
    assert "上限" in resp.json()["detail"]


def test_running_capacity_exceeded_returns_429(monkeypatch):
    monkeypatch.setattr(config, "SESSION_MAX_RUNNING", 1)
    monkeypatch.setattr(config, "SESSION_MAX", 10)

    busy = session_manager.store.create("正在跑的问题")
    session_manager.store.mark_running(busy.session_id)

    resp = client.post("/api/session/start", json={"question": "再多一个"})
    assert resp.status_code == 429
    assert "并发" in resp.json()["detail"]


def test_pipeline_exception_is_frozen_into_failed_state(monkeypatch, fake_retrieval):
    fake_retrieval()

    def boom(question, emit, **kwargs):
        raise RuntimeError("识图模型炸了")

    monkeypatch.setattr("backend.services.pipeline.run_pipeline", boom)

    session_id = client.post("/api/session/start", json={"question": "会炸的问题"}).json()["session_id"]
    final = wait_terminal(client, session_id, timeout=3)

    assert final["status"] == "failed"
    assert final["done"] is True
    assert "识图模型炸了" in final["error"]


def test_sweep_removes_expired_sessions(monkeypatch):
    monkeypatch.setattr(config, "SESSION_TTL_SEC", 0.05)

    session_manager.store.create("问题甲")
    session_manager.store.create("问题乙")
    assert session_manager.store.stats()["total"] == 2

    time.sleep(0.12)
    removed = session_manager.store.sweep_expired()

    assert removed == 2
    assert session_manager.store.stats()["total"] == 0


def test_stats_counts_by_status(monkeypatch):
    ok = session_manager.store.create("会成功")
    bad = session_manager.store.create("会失败")
    session_manager.store.succeed(ok.session_id, "方案")
    session_manager.store.fail(bad.session_id, "出错了")

    stats = session_manager.store.stats()
    assert stats["by_status"] == {"succeeded": 1, "failed": 1}
    assert stats["running"] == 0
