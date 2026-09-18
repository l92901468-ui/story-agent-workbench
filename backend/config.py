"""集中配置。

约定：环境变量只允许在本文件里读一次，其它模块一律 ``from backend import config``，
不要再散落 os.getenv。之前同一个参数在两个文件里各读一次、默认值还不一样，
排查起来很费劲。

注意：这里的值是**导入时**读取的。测试里要改，用 monkeypatch.setattr(config, "XXX", ...)。
"""
import os

SERVICE_NAME = "rag-for-company"
SERVICE_VERSION = "0.2.0"


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


# ---- 火山方舟知识库 ----
VOLC_AK = _str("VOLC_AK")
VOLC_SK = _str("VOLC_SK")
VOLC_ACCOUNT_ID = _str("VOLC_ACCOUNT_ID")
VOLC_KB_DOMAIN = _str("VOLC_KB_DOMAIN", "api-knowledgebase.mlp.cn-beijing.volces.com")
VOLC_PROJECT_NAME = _str("VOLC_PROJECT_NAME", "default")
VOLC_COLLECTION_NAME = _str("VOLC_COLLECTION_NAME", "file")

# ---- 检索 ----
# 置为 true 就完全走本地模拟，不碰火山。没配密钥时也会自动落到模拟。
RETRIEVAL_MOCK = _bool("RETRIEVAL_MOCK")
RETRIEVAL_LIMIT = _int("RETRIEVAL_LIMIT", 10)      # 交给火山的候选条数
RETRIEVAL_TOP_K = _int("RETRIEVAL_TOP_K", 5)       # 实际使用的条数
RETRIEVAL_TIMEOUT_SEC = _float("RETRIEVAL_TIMEOUT_SEC", 12)

# ---- 会话 ----
SESSION_TTL_SEC = _float("SESSION_TTL_SEC", 1800)          # 无进展超过这么久判定超时
SESSION_MAX = _int("SESSION_MAX", 500)                     # 会话总数上限
SESSION_MAX_RUNNING = _int("SESSION_MAX_RUNNING", 16)      # 同时在跑的上限（每个一个线程）

# ---- 流程节流（纯粹为了前端能看到流式效果；压测/测试里设 0 关掉） ----
STREAM_SLEEP_SEC = _float("STREAM_SLEEP_SEC", 0.05)        # 每条群聊消息之间
DRAFT_SLEEP_SEC = _float("DRAFT_SLEEP_SEC", 0.3)           # 草案阶段的人为停顿

# ---- 日志 ----
LOG_DIR = _str("LOG_DIR", "logs")
LOG_LEVEL = _str("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = _int("LOG_MAX_BYTES", 5 * 1024 * 1024)
LOG_BACKUPS = _int("LOG_BACKUPS", 3)


def volc_configured() -> bool:
    """火山密钥是否配齐。缺一样就没法签名，只能走模拟。"""
    return bool(VOLC_AK and VOLC_SK and VOLC_ACCOUNT_ID)


def retrieval_mode() -> str:
    """当前实际走哪种检索——健康检查会暴露这个值，方便一眼看出配置有没有生效。"""
    if RETRIEVAL_MOCK or not volc_configured():
        return "mock"
    return "volc"


def summary() -> dict:
    """给 /api/health 用。只暴露开关和数字，不暴露任何密钥。"""
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "retrieval_mode": retrieval_mode(),
        "volc_configured": volc_configured(),
        "retrieval_limit": RETRIEVAL_LIMIT,
        "retrieval_top_k": RETRIEVAL_TOP_K,
        "retrieval_timeout_sec": RETRIEVAL_TIMEOUT_SEC,
        "session_ttl_sec": SESSION_TTL_SEC,
        "session_max": SESSION_MAX,
        "session_max_running": SESSION_MAX_RUNNING,
        "stream_sleep_sec": STREAM_SLEEP_SEC,
        "draft_sleep_sec": DRAFT_SLEEP_SEC,
        "log_dir": LOG_DIR,
    }
