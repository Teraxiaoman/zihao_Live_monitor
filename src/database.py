"""
数据库模块：用 SQLite 记录每一段直播的起止时间。

为什么用 SQLite：零安装（Python 自带 sqlite3 模块），数据就存成一个文件，
对单机小项目最合适。等你学到第 6 步上云，换成云数据库也只是换个连接方式。

表 sessions 一条记录 = 一段完整的直播：
    start_time       开播时刻（本地时间字符串）
    end_time         下播时刻（还在播时是 NULL）
    duration_seconds 下播后算出的时长（秒）
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime

# 数据库文件放在 data/ 下，已被 .gitignore 忽略，不会误上传
DB_PATH = Path(__file__).parent.parent / "data" / "live_sessions.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # row_factory 让查询结果可以像字典一样按列名取，比下标直观
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """建表（如果还没建）。程序启动时调用一次即可。"""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rid TEXT NOT NULL,
                name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds INTEGER,
                created_at TEXT
            )
            """
        )


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_open_session(rid: str):
    """找该账号当前还没下播的记录（end_time 为 NULL 的那条）。"""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE rid=? AND end_time IS NULL "
            "ORDER BY start_time DESC LIMIT 1",
            (rid,),
        ).fetchone()
    return dict(row) if row else None


def start_session(rid: str, name: str = "") -> dict:
    """
    记录一次开播。

    如果已经有一条没下播的记录，直接返回它（防止重复插入）。
    返回这条记录的字典。
    """
    existing = get_open_session(rid)
    if existing:
        return existing
    ts = now_str()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (rid, name, start_time, created_at) VALUES (?,?,?,?)",
            (rid, name, ts, ts),
        )
        sid = cur.lastrowid
    return get_open_session(rid) or {"id": sid, "rid": rid, "name": name}


def end_session(rid: str) -> dict | None:
    """
    记录一次下播：把该账号最近一条未结束的记录补上下播时间和时长。

    返回更新后的记录；如果根本找不到未结束的记录（比如程序之前崩了没记下开播），
    返回 None，由调用方决定怎么提示。
    """
    open_s = get_open_session(rid)
    if not open_s:
        return None
    end = now_str()
    start_dt = datetime.strptime(open_s["start_time"], "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
    duration = int((end_dt - start_dt).total_seconds())
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET end_time=?, duration_seconds=? WHERE id=?",
            (end, duration, open_s["id"]),
        )
    return {**open_s, "end_time": end, "duration_seconds": duration}


if __name__ == "__main__":
    # 自测：python src/database.py
    init_db()
    print("建表完成。数据库位置：", DB_PATH)
