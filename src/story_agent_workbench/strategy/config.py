"""Config loader for stage-5 routing and reply strategy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class StrategyConfig:
    route_graph_keywords: list[str] = field(
        default_factory=lambda: ["关系", "阵营", "全局", "链条", "关联", "谁和谁", "哪些人物"]
    )
    route_text_keywords: list[str] = field(
        default_factory=lambda: ["原文", "句子", "改写", "措辞", "段落", "scene", "证据"]
    )
    route_graph_threshold: float = 0.3
    route_text_threshold: float = 0.2

    auto_mode_enabled: bool = True
    mode_keywords: dict[str, list[str]] = field(
        default_factory=lambda: {
            "feedback": ["建议", "改写", "优化", "怎么改"],
            "critic": ["冲突", "矛盾", "不一致", "漏洞"],
            "evidence": ["证据", "出处", "原文", "依据", "引用"],
        }
    )

    show_full_evidence_modes: list[str] = field(default_factory=lambda: ["evidence"])

    graph_conf_threshold: float = 0.45
    text_conf_threshold: float = 0.35
    low_confidence_threshold: float = 0.25


DEFAULT_STRATEGY_PATH = Path("config/strategy.json")


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for k, v in updates.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_strategy_config(path: Path | str | None = None) -> StrategyConfig:
    cfg = StrategyConfig()
    config_path = Path(path) if path else DEFAULT_STRATEGY_PATH

    if not config_path.exists():
        return cfg

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return cfg

    base = {
        "route_graph_keywords": cfg.route_graph_keywords,
        "route_text_keywords": cfg.route_text_keywords,
        "route_graph_threshold": cfg.route_graph_threshold,
        "route_text_threshold": cfg.route_text_threshold,
        "auto_mode_enabled": cfg.auto_mode_enabled,
        "mode_keywords": cfg.mode_keywords,
        "show_full_evidence_modes": cfg.show_full_evidence_modes,
        "graph_conf_threshold": cfg.graph_conf_threshold,
        "text_conf_threshold": cfg.text_conf_threshold,
        "low_confidence_threshold": cfg.low_confidence_threshold,
    }

    merged = _deep_update(base, raw)

    return StrategyConfig(
        route_graph_keywords=list(merged.get("route_graph_keywords", [])),
        route_text_keywords=list(merged.get("route_text_keywords", [])),
        route_graph_threshold=float(merged.get("route_graph_threshold", 0.3)),
        route_text_threshold=float(merged.get("route_text_threshold", 0.2)),
        auto_mode_enabled=bool(merged.get("auto_mode_enabled", True)),
        mode_keywords=dict(merged.get("mode_keywords", {})),
        show_full_evidence_modes=list(merged.get("show_full_evidence_modes", ["evidence"])),
        graph_conf_threshold=float(merged.get("graph_conf_threshold", 0.45)),
        text_conf_threshold=float(merged.get("text_conf_threshold", 0.35)),
        low_confidence_threshold=float(merged.get("low_confidence_threshold", 0.25)),
    )
