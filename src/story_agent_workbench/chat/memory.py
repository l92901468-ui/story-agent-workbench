"""Minimal file-based session memory for chat layer (stage 3.6)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SESSION_DIR = Path('.story_agent_sessions')
SAFE_SESSION_RE = re.compile(r'[^a-zA-Z0-9_.-]+')


def _session_file(session_id: str) -> Path:
    safe = SAFE_SESSION_RE.sub('_', session_id.strip() or 'default')
    return SESSION_DIR / f'{safe}.json'


def load_recent_turns(session_id: str, max_turns: int) -> list[dict[str, Any]]:
    """Load the latest max_turns entries for a session."""

    file_path = _session_file(session_id)
    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding='utf-8'))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    turns = [item for item in data if isinstance(item, dict)]
    return turns[-max(0, max_turns):]


def append_turn(
    *,
    session_id: str,
    mode: str,
    user_query: str,
    assistant_reply: str,
    keep_turns: int,
) -> None:
    """Append one turn and keep only the latest keep_turns records."""

    file_path = _session_file(session_id)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    turns = load_recent_turns(session_id, max_turns=max(keep_turns, 0))
    turns.append(
        {
            'mode': mode,
            'user': user_query,
            'assistant': assistant_reply,
        }
    )
    turns = turns[-max(1, keep_turns):]

    file_path.write_text(json.dumps(turns, ensure_ascii=False, indent=2), encoding='utf-8')
