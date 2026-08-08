"""
实时推送开关状态管理。

monitor.py 和 serve.py 共用同一个文件，保证：
- 网页上关闭推送后，monitor 不再发微信；
- monitor 重启后，开关状态仍然保持。

状态文件：data/push_state.json
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
STATE_PATH = ROOT / "data" / "push_state.json"


def _load() -> dict:
    if STATE_PATH.exists():
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_enabled() -> bool:
    """推送是否开启。默认开启。"""
    return bool(_load().get("enabled", True))


def set_enabled(enabled: bool) -> None:
    """设置推送开关。"""
    state = _load()
    state["enabled"] = bool(enabled)
    _save(state)


def toggle() -> bool:
    """翻转开关，返回新的状态。"""
    new = not is_enabled()
    set_enabled(new)
    return new
