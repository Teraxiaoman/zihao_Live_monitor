"""
主程序：持续监测直播状态，发生变化时推送微信，并把每段直播的起止时间写进数据库。

用法：
    python monitor.py                  # 无限循环监测（7×24 跑这个）
    python monitor.py --once           # 只跑一轮就退出（验证/调试）
    python monitor.py --test-push      # 发一条测试微信，确认推送通不通
    python monitor.py --report         # 打印本月开播时长 / 距目标 / 日均报告
    MONITOR_DRYRUN=1 python monitor.py --once   # 测试模式：写库但不真发微信
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 让 Python 找到 src 里的模块
sys.path.insert(0, str(Path(__file__).parent / "src"))

from douyin import create_session, fetch_live_status
from notify import push
from database import init_db, start_session, end_session, get_open_session
from analytics import build_report, format_hours
from push_state import is_enabled

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.json"
STATE_PATH = ROOT / "data" / "state.json"


def load_config() -> dict:
    # 云端优先：用环境变量提供配置（不含密钥，可安全公开）
    env_accounts = os.environ.get("MONITOR_ACCOUNTS")
    if env_accounts:
        try:
            accounts = json.loads(env_accounts)
        except json.JSONDecodeError:
            print("⚠️ MONITOR_ACCOUNTS 不是合法 JSON，退出。")
            sys.exit(1)
        target = int(os.environ.get("MONITOR_TARGET_HOURS", "156"))
        return {"accounts": accounts, "monthly_target_hours": target}

    # 本地：读 config.json
    if not CONFIG_PATH.exists():
        print("找不到 config.json！请把 config.example.json 复制为 config.json 再填。")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state() -> dict:
    if STATE_PATH.exists():
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: int) -> str:
    """把秒数转成中国人习惯的读法，如 '2小时15分' 或 '45分30秒'。"""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}小时{m}分"
    if m:
        return f"{m}分{s}秒"
    return f"{s}秒"


def on_state_change(acc: dict, status, sendkey: str) -> None:
    """状态发生变化（开播或下播）时调用：写库 + 推送。"""
    who = acc.get("name") or status.nickname or acc["rid"]
    rid = acc["rid"]
    if status.is_living:
        # 开播：插入一条新记录
        start_session(rid, who)
        title = f"🔴 {who} 开播啦！"
        content = (
            f"**{who}** 刚刚开播\n"
            f"> 标题：{status.title or '（无标题）'}\n"
            f"> 在线：{status.user_count or '未知'}\n"
            f"> 时间：{now_str()}"
        )
    else:
        # 下播：补上下播时间和时长
        rec = end_session(rid)
        if rec:
            dur_text = format_duration(rec["duration_seconds"])
            # 短场标记：不足 1 小时不计入月度时长
            short = rec["duration_seconds"] < 3600
        else:
            dur_text = "（未记录到对应的开播，无法计算时长）"
            short = False
        title = f"⚪ {who} 下播了"
        content = (
            f"**{who}** 刚刚下播\n"
            f"> 本次直播时长：{dur_text}\n"
            + ("> ⚠️ 不足 1 小时，不计入月度时长\n" if short else "")
            + f"> 时间：{now_str()}"
        )
    if is_enabled():
        push(title, content, sendkey)
    else:
        print(f"    🔕 推送已关闭，不发微信：{title}")


def check_all(config: dict, session, state: dict, sendkey: str) -> dict:
    """查一轮所有账号，处理变化，返回更新后的 state。"""
    for acc in config["accounts"]:
        rid = acc["rid"]
        status = fetch_live_status(rid, session=session)
        print(f"  {status.describe()}")

        if not status.ok:
            # 查询失败：先打印告警，但不改变记录的"上次状态"，
            # 以免一次网络抖动就误报"下播"。
            print(f"    ⚠️ 查询失败：{status.error}")
            continue

        prev_living = state.get(rid, {}).get("is_living", False)
        if status.is_living != prev_living:
            print(f"    🔔 状态变化：{prev_living} -> {status.is_living}")
            on_state_change(acc, status, sendkey)
            state[rid] = {"is_living": status.is_living, "updated_at": now_str()}
        else:
            # 没变化：仅在第一次见到该账号时记下初始状态
            if rid not in state:
                state[rid] = {"is_living": status.is_living, "updated_at": now_str()}

        time.sleep(1)  # 两个号之间隔开，降低被风控概率
    return state


def print_report(rep: dict) -> None:
    """把 build_report 返回的字典，打印成人在终端里能直接看懂的报告。"""
    y, m = rep["year"], rep["month"]
    print(f"\n===== {y} 年 {m} 月开播时长报告 =====")
    print(f"本月已播：{format_hours(rep['done_hours'])}  （{rep['done_hours']} 小时）")
    print(f"月度目标：{format_hours(rep['target_hours'])}  （{rep['target_hours']} 小时）")
    print(f"完成进度：{rep['progress_percent']}%")
    if rep["is_current_month"]:
        print(f"距目标还差：{format_hours(rep['remain_hours'])}  （{rep['remain_hours']} 小时）")
        print(f"本月剩余天数（含今日）：{rep['days_left']} 天")
        print(f"剩余每天需播：{format_hours(rep['daily_need_hours'])}  （{rep['daily_need_hours']} 小时/天）")
    else:
        print('（这是历史月份，无"剩余天数 / 日均"数据）')
    print("=====================================\n")


def main() -> None:
    config = load_config()

    if "--report" in sys.argv:
        init_db()
        rids = [a["rid"] for a in config["accounts"]]
        target = config.get("monthly_target_hours", 0)
        now = datetime.now()
        print_report(build_report(now.year, now.month, target, rids))
        return

    # 测试模式：设了 MONITOR_DRYRUN 环境变量就不真发微信，只写库+打印
    dry_run = os.environ.get("MONITOR_DRYRUN") == "1"
    # 云端：优先环境变量 SERVERCHAN_KEY（GitHub Secrets 注入）；本地回退 config.json
    sendkey = "" if dry_run else (os.environ.get("SERVERCHAN_KEY") or config.get("serverchan_key", ""))
    interval = max(10, int(config.get("check_interval_seconds", 60)))
    state = load_state()
    session = create_session()
    init_db()

    if "--test-push" in sys.argv:
        push("✅ 推送测试", "如果你在微信里收到这条，说明 Server酱 配置成功！", sendkey)
        return

    if not sendkey and not dry_run:
        print("⚠️ 未配置 serverchan_key，推送将以[演练]形式打印，不会真发到微信。")

    # 启动补偿：state 说"在播"，但库里没有对应的未结束记录时，
    # 补建一条，避免程序上次崩溃导致这段直播时长丢失。
    for acc in config["accounts"]:
        rid = acc["rid"]
        if state.get(rid, {}).get("is_living", False) and not get_open_session(rid):
            print(f"    🛠️ 补偿：{acc.get('name')} 状态为在播但库里无记录，补建一条")
            start_session(rid, acc.get("name") or rid)

    if "--once" in sys.argv:
        print("单次运行模式……")
        state = check_all(config, session, state, sendkey)
        save_state(state)
        print("完成。")
        return

    print(f"开始持续监测（间隔 {interval}s）。按 Ctrl+C 停止。")
    while True:
        try:
            state = check_all(config, session, state, sendkey)
            save_state(state)
        except Exception as exc:
            print(f"本轮异常：{exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
