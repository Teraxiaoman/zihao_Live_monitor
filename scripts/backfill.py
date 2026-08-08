"""
历史数据回填工具：把过去的开播记录补进数据库。

【什么时候用】
你想让报告从一开始就包含历史数据（比如系统搭好之前「子浩」就已经播了好几天），
但抖音接口拿不到历史，只能靠你记得的大概时间手动补。

【怎么用】
1. 把下面的 HISTORY 列表改成你记得的真实起止时间
2. 运行：  python backfill.py
每条记录格式：(抖音号, 开播时间, 下播时间)
时间格式固定 "YYYY-MM-DD HH:MM:SS"（24 小时制）

【昵称从哪来】
昵称不再手填，而是自动从 config.json 的 accounts 里按抖音号匹配，
改主播昵称只需改 config.json，这里不用动。

【注意】
- 只是"补录"，不会重复计算 monitor 自动记的场次
- 时间填错（比如下播早于开播）会导致时长算成负数，填的时候留意一下
- 时长(duration_seconds)会在这里自动算好，看板不会再误显示"进行中"
"""
from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from database import init_db, _connect

FMT = "%Y-%m-%d %H:%M:%S"
CONFIG_PATH = Path(__file__).parent.parent / "config.json"

# ↓↓↓ 改这里：把你记得的历史开播记录填进去（没有就留空列表 []）↓↓↓
# 这些场次来自 2026-08-08 用户提供的直播历史截图。
# 截图里 "幻想不是止痛药" 带引号，判断是直播标题而非主播名，全部挂到大号下。
# 如果发现有小号场次，把那一行的抖音号改成 "zihaolaoshi" 即可。
HISTORY = [
    ("Zihaolaoshi.", "2026-08-01 20:17:00", "2026-08-01 22:17:00"),
    ("Zihaolaoshi.", "2026-08-01 23:18:00", "2026-08-02 02:29:00"),
    ("Zihaolaoshi.", "2026-08-02 18:57:00", "2026-08-02 22:00:00"),
    ("Zihaolaoshi.", "2026-08-02 23:20:00", "2026-08-03 02:21:00"),
    ("Zihaolaoshi.", "2026-08-03 19:04:00", "2026-08-03 22:04:00"),
    ("Zihaolaoshi.", "2026-08-03 23:02:00", "2026-08-04 02:04:00"),
    ("Zihaolaoshi.", "2026-08-04 19:35:00", "2026-08-04 22:37:00"),
    ("Zihaolaoshi.", "2026-08-04 23:18:00", "2026-08-05 01:29:00"),
    ("Zihaolaoshi.", "2026-08-05 19:13:00", "2026-08-05 22:21:00"),
    ("Zihaolaoshi.", "2026-08-05 23:21:00", "2026-08-06 01:11:00"),
    ("Zihaolaoshi.", "2026-08-06 23:14:00", "2026-08-07 00:24:00"),
    ("Zihaolaoshi.", "2026-08-07 03:08:00", "2026-08-07 04:10:00"),
    ("Zihaolaoshi.", "2026-08-07 19:03:00", "2026-08-07 22:08:00"),
]
# ↑↑↑ 改这里 ↑↑↑


def load_names() -> dict:
    """从 config.json 读出 抖音号 -> 昵称 的映射。"""
    try:
        cfg = json.load(open(CONFIG_PATH, encoding="utf-8"))
        return {a["rid"]: a.get("name", a["rid"]) for a in cfg["accounts"]}
    except Exception:
        return {}


def main() -> None:
    if not HISTORY:
        print("HISTORY 列表是空的。打开本文件，把记得的历史开播时间填进去再运行。")
        return
    names = load_names()
    init_db()
    n = 0
    with _connect() as conn:
        for rid, s, e in HISTORY:
            name = names.get(rid, rid)
            dur = int((datetime.strptime(e, FMT) - datetime.strptime(s, FMT)).total_seconds())
            conn.execute(
                "INSERT INTO sessions (rid, name, start_time, end_time, duration_seconds, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (rid, name, s, e, dur, s),
            )
            print(f"已补录：{name}  {s}  →  {e}  ({dur//3600}小时{dur%3600//60}分)")
            n += 1
    print(f"\n回填完成，共 {n} 场！现在跑  python monitor.py --report  就能看到历史累计了。")


if __name__ == "__main__":
    main()
