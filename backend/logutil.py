"""结构化日志。

之前这个项目全程没有日志：流程走到哪个阶段、检索走了火山还是本地模拟、
会话为什么卡住，全靠猜。统一出口在这里——控制台 + LOG_DIR/<logger>.log 双写，
按大小轮转。

logger 名刻意用固定的几个（api / pipeline / session / knowledge_base），
不按会话 id 起名字，否则会话一多会生成一堆日志文件。
"""
import logging
import os
from logging.handlers import RotatingFileHandler

from backend import config

_FMT = logging.Formatter(
    fmt="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

API = "api"
PIPELINE = "pipeline"
SESSION = "session"
KNOWLEDGE_BASE = "knowledge_base"

_ready: set = set()


def get_logger(name: str) -> logging.Logger:
    """按名字取 logger，首次调用时挂好 handler，之后幂等。"""
    logger = logging.getLogger(name)
    if name in _ready:
        return logger

    logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    if not logger.handlers:
        console = logging.StreamHandler()
        console.setFormatter(_FMT)
        logger.addHandler(console)

        if config.LOG_DIR:
            os.makedirs(config.LOG_DIR, exist_ok=True)
            file_handler = RotatingFileHandler(
                os.path.join(config.LOG_DIR, f"{name}.log"),
                maxBytes=config.LOG_MAX_BYTES,
                backupCount=config.LOG_BACKUPS,
                encoding="utf-8",
            )
            file_handler.setFormatter(_FMT)
            logger.addHandler(file_handler)

    _ready.add(name)
    return logger
