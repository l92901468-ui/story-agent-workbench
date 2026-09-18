import json
import sys

import pytest

from backend import config
from backend.services import knowledge_base


def test_build_search_payload_contains_question():
    payload = knowledge_base.build_search_payload("测试问题")
    assert payload["query"] == "测试问题"
    assert payload["pre_processing"]["messages"][1]["content"] == "测试问题"


def test_prepare_request_writes_json_body():
    req = knowledge_base.prepare_request("POST", "/x", data={"k": "v"})
    body = json.loads(req.body)
    assert body == {"k": "v"}
    assert req.method == "POST"


def test_retrieve_uses_mock_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(config, "VOLC_AK", "")
    monkeypatch.setattr(config, "VOLC_SK", "")
    monkeypatch.setattr(config, "VOLC_ACCOUNT_ID", "")

    result = knowledge_base.retrieve("测试问题")
    assert result.source == "mock"
    assert result.items, "没有凭据也要有内容，否则下游整个流程空转"
    assert result.error is None


def test_retrieve_exposes_error_when_volc_fails(monkeypatch):
    """以前这种情况返回空 list，调用方完全看不出是炸了还是没数据。"""
    monkeypatch.setattr(config, "VOLC_AK", "ak")
    monkeypatch.setattr(config, "VOLC_SK", "sk")
    monkeypatch.setattr(config, "VOLC_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "RETRIEVAL_MOCK", False)

    def boom(_question):
        raise knowledge_base.RetrievalError("连接被拒")

    monkeypatch.setattr(knowledge_base, "search_knowledge_volc", boom)

    result = knowledge_base.retrieve("测试问题")
    assert result.source == "mock"          # 降级保证流程还能跑
    assert result.error == "连接被拒"        # 但原因必须带出来
    assert "回退本地模拟" in result.note


def test_search_knowledge_volc_raises_rather_than_swallowing(monkeypatch):
    monkeypatch.setattr(knowledge_base.requests, "request", lambda **kwargs: (_ for _ in ()).throw(OSError("timeout")))

    with pytest.raises(knowledge_base.RetrievalError):
        knowledge_base.search_knowledge_volc("测试问题")


def test_request_object_works_without_sdk(monkeypatch):
    """没装 volcengine 时请求对象由内置替身接管，字段必须还是完整的。

    之前这一步强依赖 SDK，导致纯 mock 场景也必须装包。
    """
    monkeypatch.setattr(knowledge_base, "_new_request", lambda: knowledge_base._SimpleRequest())

    req = knowledge_base.prepare_request("POST", "/x", data={"k": "v"})
    assert json.loads(req.body) == {"k": "v"}
    assert req.method == "POST"
    assert req.headers["Content-Type"] == "application/json; charset=utf-8"


def test_missing_sdk_gives_actionable_error(monkeypatch):
    """配了密钥却没装 volcengine 时，错误信息要直接告诉人该装什么。"""
    monkeypatch.setattr(config, "VOLC_AK", "ak")
    monkeypatch.setattr(config, "VOLC_SK", "sk")
    monkeypatch.setattr(config, "VOLC_ACCOUNT_ID", "acct")
    monkeypatch.setattr(config, "RETRIEVAL_MOCK", False)
    monkeypatch.setitem(sys.modules, "volcengine.base.Request", None)
    monkeypatch.setitem(sys.modules, "volcengine.Credentials", None)

    with pytest.raises(knowledge_base.RetrievalError) as caught:
        knowledge_base.prepare_request("POST", "/x", data={"k": "v"})

    assert "pip install volcengine" in str(caught.value)


def test_top_k_truncates_records(monkeypatch):
    monkeypatch.setattr(config, "RETRIEVAL_TOP_K", 2)

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"title": f"t{i}", "snippet": "s"} for i in range(5)]}

    monkeypatch.setattr(knowledge_base.requests, "request", lambda **kwargs: FakeResponse())

    items = knowledge_base.search_knowledge_volc("测试问题")
    assert len(items) == 2
