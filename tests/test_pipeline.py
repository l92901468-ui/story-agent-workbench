from fastapi.testclient import TestClient

from backend.app import app
from tests.conftest import wait_terminal

client = TestClient(app)


def test_health_reports_config_and_sessions():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    # 不再是写死的 {"status": "ok"}：配置走向和会话水位都要能看到
    assert "retrieval_mode" in body["config"]
    assert "total" in body["sessions"]
    assert "uptime_sec" in body


def test_health_reflects_session_water_mark():
    from backend.services import session_manager

    session_manager.store.create("问题一")
    session_manager.store.create("问题二")

    body = client.get("/api/health").json()
    assert body["sessions"]["total"] == 2
    assert body["sessions"]["by_status"]["pending"] == 2


def test_request_id_is_injected():
    resp = client.get("/api/health")
    assert "X-Request-Id" in resp.headers

    resp = client.get("/api/health", headers={"X-Request-Id": "abc123"})
    assert resp.headers["X-Request-Id"] == "abc123"


def test_pipeline_success(fake_retrieval):
    fake_retrieval()

    resp = client.post("/api/pipeline", json={"question": "给我一个初中研学方案"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["five_focus_drafts"]) == 5
    assert len(data["group_chat_round_1"]) == 10
    assert len(data["group_chat_round_2"]) == 10
    assert data["final_solution"].startswith("综合执行方案")
    assert data["retrieval_source"] == "fake"


def test_pipeline_response_carries_stage_timings(fake_retrieval):
    fake_retrieval()

    data = client.post("/api/pipeline", json={"question": "设计研学路线"}).json()
    # 五个阶段都有耗时记录，方便定位慢在哪一步
    assert set(data["stage_timings_ms"]) == {"retrieve", "draft", "discuss", "reconcile", "finalize"}


def test_session_event_flow(fake_retrieval):
    fake_retrieval()

    start = client.post("/api/session/start", json={"question": "设计研学路线"})
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    final = wait_terminal(client, session_id)
    assert final["status"] == "succeeded"
    assert final["final_solution"].startswith("综合执行方案")
    assert final["event_count"] > 0


def test_session_events_are_incremental_and_marked_by_stage(fake_retrieval):
    fake_retrieval()

    session_id = client.post("/api/session/start", json={"question": "设计研学路线"}).json()["session_id"]
    wait_terminal(client, session_id)

    events = client.get(f"/api/session/{session_id}/events?cursor=0").json()
    body_events = events["events"]
    assert body_events, "至少应该有事件"

    stages = [e["stage"] for e in body_events if e["type"] == "stage" and e["status"] == "start"]
    assert stages == ["retrieve", "draft", "discuss", "reconcile", "finalize"]

    # 游标前进后同一批事件不能重复拉到
    cursor = events["next_cursor"]
    again = client.get(f"/api/session/{session_id}/events?cursor={cursor}").json()
    assert again["events"] == []


def test_session_not_found():
    assert client.get("/api/session/does-not-exist").status_code == 404
    assert client.get("/api/session/does-not-exist/events").status_code == 404
