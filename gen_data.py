"""
生成看板数据：把"各主播当前状态 + 本月时长统计 + 历史场次"打包成 dashboard/data.json。

设计说明（这一步的核心知识点）：
    网页（前端）不能直接 import Python 模块，它只能通过 HTTP 拿到一份 JSON。
    所以这个脚本就是"后端到前端的翻译层"——把我们已经写好的
    analytics / database / douyin 的结果，变成前端能直接用的数据。

用法：
    python gen_data.py            # 生成一份 data.json
    （monitor 跑的时候也会调用本函数，让看板保持最新）

未来上云（第 6 步）时，CI 定时跑这个脚本、把 data.json 推到 GitHub Pages 即可，
前端代码一行都不用改。这就是"数据(JSON) 与 页面(HTML) 分离"的好处。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

from database import init_db, _connect
from analytics import build_report, format_hours
from douyin import create_session, fetch_live_status

CONFIG_PATH = ROOT / "config.json"
OUT_PATH = ROOT / "dashboard" / "data.json"


def load_config() -> dict:
    # 云端优先：用环境变量提供配置（不含密钥）
    env_accounts = os.environ.get("MONITOR_ACCOUNTS")
    if env_accounts:
        accounts = json.loads(env_accounts)
        target = int(os.environ.get("MONITOR_TARGET_HOURS", "156"))
        return {"accounts": accounts, "monthly_target_hours": target}

    # 本地：读 config.json
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    config = load_config()
    init_db()
    accounts = config["accounts"]
    rids = [a["rid"] for a in accounts]
    target = config.get("monthly_target_hours", 0)
    now = datetime.now()

    # 1) 本月时长统计（复用 analytics，命令行和网页数字永远一致）
    report = build_report(now.year, now.month, target, rids)

    # 2) 各主播当前开播状态（实时查一次；频率低，风控无忧）
    nick = {a["rid"]: (a.get("name") or a["rid"]) for a in accounts}
    avatar_by_nick = {a.get("name"): a.get("avatar", "") for a in accounts}
    session = create_session()
    statuses = []
    for a in accounts:
        rid = a["rid"]
        info = fetch_live_status(rid, session=session)
        if info.ok:
            statuses.append({
                "rid": rid,
                "nickname": nick[rid],
                "avatar": a.get("avatar", ""),
                "is_living": info.is_living,
                "title": info.title,
                "user_count": info.user_count,
            })
        else:
            # 查询失败也给出记录，前端显示为"状态未知"，不中断看板
            statuses.append({
                "rid": rid,
                "nickname": nick[rid],
                "avatar": a.get("avatar", ""),
                "is_living": False,
                "title": "",
                "user_count": "",
                "error": info.error,
            })

    # 3) 历史场次（含正在播的那段：end_time 为空 → 显示"进行中"）
    sessions = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, rid, name, start_time, end_time, duration_seconds "
            "FROM sessions ORDER BY start_time DESC"
        ).fetchall()
    for r in rows:
        s, e, dur = r["start_time"], r["end_time"], r["duration_seconds"]
        # 时长优先用已存的 duration_seconds；缺失但有结束时间时当场算（防止回填漏算导致显示"进行中"）
        if dur is not None:
            dur_text = format_hours(dur / 3600)
        elif e:
            secs = (datetime.strptime(e, FMT) - datetime.strptime(s, FMT)).total_seconds()
            dur_text = format_hours(secs / 3600)
        else:
            dur_text = "进行中"
        sessions.append({
            "id": r["id"],
            "rid": r["rid"],
            "nickname": r["name"],
            "avatar": avatar_by_nick.get(r["name"], ""),
            "start": s,
            "end": e or "进行中",
            "duration": dur_text,
        })

    data = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "report": report,
        "accounts": statuses,
        "sessions": sessions,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # 额外生成 data.js：把同一份数据塞进 window.__DASHBOARD_DATA__，
    # 这样即使直接双击 index.html（file:// 协议，fetch 会被浏览器拦截）也能显示离线数据。
    with open(OUT_PATH.with_suffix(".js"), "w", encoding="utf-8") as f:
        f.write("window.__DASHBOARD_DATA__ = ")
        json.dump(data, f, ensure_ascii=False)
        f.write(";")
    print(f"已生成 {OUT_PATH} 及 data.js  |  账号 {len(statuses)} 个  |  历史场次 {len(sessions)} 场")


if __name__ == "__main__":
    main()
