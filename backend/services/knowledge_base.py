"""知识库检索层。

对外只有两个入口：
    retrieve(question) -> RetrievalResult    策略层：决定走火山还是本地模拟
    search_knowledge_volc(question) -> list  传输层：只管把火山那个 HTTP 调用打出去

改动要点：
    1. volcengine SDK 改成**惰性导入**。原来写在模块顶层，导致跑纯 mock 的单测
       也必须装 SDK，装不上连 pytest 都起不来。
    2. 原来无论「没检索到」还是「调用炸了」都返回空 list，调用方分不清，
       日志里也看不出来。现在用 RetrievalResult 把来源（source）和失败原因
       （error / note）一起带出去。
"""
import json
import time
from dataclasses import dataclass

import requests

from backend import config
from backend.logutil import get_logger

log = get_logger("knowledge_base")

SEARCH_PATH = "/api/knowledge/collection/search_knowledge"

DIMENSIONS = ["后勤", "评价", "方案", "成果", "资源", "执行", "安全", "课程", "研学"]


class RetrievalError(RuntimeError):
    """检索失败。以前这种情况被吞成空 list，现在明确抛出来。"""


@dataclass
class RetrievalResult:
    """一次检索的完整结果，不只是那一堆片段。"""

    items: list
    source: str                 # volc / mock
    elapsed_ms: float
    note: str = ""              # 为什么走到了这条路
    error: str = None           # 失败原因；成功时为 None

    def __post_init__(self):
        if self.items is None:
            self.items = []


def prepare_request(method: str, path: str, params: dict = None, data: dict = None):
    """组装一个待签名的火山请求对象。不发包，纯构造，方便单测。"""
    domain = config.VOLC_KB_DOMAIN

    if params:
        for key, value in params.items():
            if isinstance(value, (int, float, bool)):
                params[key] = str(value)
            elif isinstance(value, list):
                params[key] = ",".join([str(item) for item in value])

    req = _new_request()
    req.set_shema("http")
    req.set_method(method)
    req.set_connection_timeout(10)
    req.set_socket_timeout(10)
    req.set_headers(
        {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Host": domain,
            "V-Account-Id": config.VOLC_ACCOUNT_ID,
        }
    )

    if params:
        req.set_query(params)
    req.set_host(domain)
    req.set_path(path)

    if data is not None:
        req.set_body(json.dumps(data, ensure_ascii=False))

    if config.VOLC_AK and config.VOLC_SK:
        # 惰性导入：只有真正要用 AK/SK 签名才需要 volcengine 基础包。
        try:
            from volcengine.Credentials import Credentials
            from volcengine.auth.SignerV4 import SignerV4
        except ImportError as exc:
            raise RetrievalError(
                "已配置 VOLC_AK/VOLC_SK，需要安装 volcengine 才能签名：pip install volcengine"
            ) from exc

        credentials = Credentials(config.VOLC_AK, config.VOLC_SK, "air", "cn-north-1")
        SignerV4.sign(req, credentials)

    return req


class _SimpleRequest:
    """请求对象的最小替身。

    接口面覆盖本模块实际用到的部分。存在的意义是让**不签名**的场景
    （本地模拟、单元测试、纯 mock 部署）不必安装 volcengine SDK——
    之前即使不签名也要构造 volcengine.base.Request，等于这个包成了硬依赖。
    """

    def __init__(self):
        self.schema = "http"
        self.method = ""
        self.host = ""
        self.path = ""
        self.headers = {}
        self.query = {}
        self.body = ""
        self.connection_timeout = 10
        self.socket_timeout = 10

    def set_shema(self, value):
        self.schema = value

    def set_method(self, value):
        self.method = value

    def set_host(self, value):
        self.host = value

    def set_path(self, value):
        self.path = value

    def set_headers(self, value):
        self.headers = dict(value)

    def set_query(self, value):
        self.query = value

    def set_body(self, value):
        self.body = value

    def set_connection_timeout(self, value):
        self.connection_timeout = value

    def set_socket_timeout(self, value):
        self.socket_timeout = value


def _new_request():
    """有官方 SDK 就用它的 Request（签名依赖它），装不了就退回内置最小实现。"""
    try:
        from volcengine.base.Request import Request

        return Request()
    except ImportError:
        return _SimpleRequest()


def build_search_payload(question: str) -> dict:
    return {
        "project": config.VOLC_PROJECT_NAME,
        "name": config.VOLC_COLLECTION_NAME,
        "query": question,
        "limit": config.RETRIEVAL_LIMIT,
        "pre_processing": {
            "need_instruction": True,
            "return_token_usage": True,
            "messages": [{"role": "system", "content": ""}, {"role": "user", "content": question}],
        },
        "dense_weight": 0.5,
        "post_processing": {
            "get_attachment_link": True,
            "rerank_only_chunk": False,
            "rerank_switch": False,
        },
    }


def generate_mock_retrieval(question: str) -> list:
    """本地模拟的检索片段。没有知识库凭据时用这个顶上，保证流程能跑通。"""
    return [
        {
            "title": f"相关材料 {idx + 1}",
            "snippet": f"围绕问题“{question}”的检索片段，强调{DIMENSIONS[idx]}维度。",
        }
        for idx in range(3)
    ]


def search_knowledge_volc(question: str) -> list:
    """调火山知识库。**失败会抛 RetrievalError**，不静默返回空列表。"""
    domain = config.VOLC_KB_DOMAIN
    payload = build_search_payload(question)
    req = prepare_request("POST", SEARCH_PATH, data=payload)

    started = time.perf_counter()
    try:
        response = requests.request(
            method=req.method,
            url=f"http://{domain}{req.path}",
            headers=req.headers,
            data=req.body,
            timeout=config.RETRIEVAL_TIMEOUT_SEC,
        )
        response.raise_for_status()
        body = response.json()
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        log.warning(f"火山知识库调用失败 耗时={elapsed_ms}ms 原因={exc}")
        raise RetrievalError(str(exc)) from exc

    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    records = body.get("data", [])
    if not isinstance(records, list):
        raise RetrievalError(f"返回结构不符合预期：data 字段类型为 {type(body.get('data')).__name__}")

    items = records[: config.RETRIEVAL_TOP_K]
    log.info(f"火山检索完成 命中={len(records)} 使用={len(items)} 耗时={elapsed_ms}ms")
    return items


def retrieve(question: str) -> RetrievalResult:
    """策略层：决定这次检索走哪条路，并把为什么走这条路记下来。"""
    if config.retrieval_mode() == "mock":
        started = time.perf_counter()
        items = generate_mock_retrieval(question)
        return RetrievalResult(
            items=items,
            source="mock",
            elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
            note="未配置火山密钥或显式开启了 RETRIEVAL_MOCK，使用本地模拟检索",
        )

    started = time.perf_counter()
    try:
        items = search_knowledge_volc(question)
        if items:
            return RetrievalResult(items=items, source="volc", elapsed_ms=round((time.perf_counter() - started) * 1000, 1))
        return _fallback(question, started, "火山返回 0 条，回退本地模拟")
    except RetrievalError as exc:
        note = f"火山调用失败，回退本地模拟：{exc}"
        log.warning(note)
        return _fallback(question, started, note, error=str(exc))


def _fallback(question: str, started: float, note: str, error: str = None) -> RetrievalResult:
    return RetrievalResult(
        items=generate_mock_retrieval(question),
        source="mock",
        elapsed_ms=round((time.perf_counter() - started) * 1000, 1),
        note=note,
        error=error,
    )
