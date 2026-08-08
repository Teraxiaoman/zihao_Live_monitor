"""
统计模块：把 database 里记录的直播时段，算成你真正关心的数字。

这里藏着这个项目最值钱的几个"真实业务坑"，我一个一个都处理了：

1. 跨天直播拆分：
   一场直播从 8/31 23:00 开播、9/1 01:00 下播，算"8 月时长"时
   只能算 8/31 23:00→24:00 这 1 小时，不能把整 2 小时都塞进 8 月。
   做法：把每段直播的区间，和"本月这个区间"求【交集】。

2. 正在播的那段：
   主播现在还开着播，end_time 是空（NULL），它的时长还在涨。
   算"本月已播"时必须把"从开播到现在"这部分也算进去，否则统计会少一块。

3. 剩余天数包含当日（你特别强调的）：
   今天是 8/8，本月还剩 8,9,…,31 共 24 天 —— 把 8 号当天算进去，
   公式是：本月天数 - 今天日期 + 1。
"""
from __future__ import annotations

from datetime import datetime

from database import _connect

FMT = "%Y-%m-%d %H:%M:%S"

# 单场直播低于这个时长（秒）的不计入月度统计，默认 1 小时。
# 用途：排除"秒开秒关"的查询误判，以及主播短暂露脸不足 1 小时的场次。
# 想改成 30 分钟就把这里改成 1800；正在播的场次（end_time 为空）时长未定，不在此过滤范围内。
MIN_SESSION_SECONDS = 3600


def _parse(s: str | None) -> datetime | None:
    """把数据库里的时间字符串转成 datetime；空值返回 None。"""
    return datetime.strptime(s, FMT) if s else None


def month_bounds(year: int, month: int):
    """返回 (本月起点, 下月起点) 两个 datetime。区间 [start, nxt) 就是整月。"""
    start = datetime(year, month, 1)
    nxt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, nxt


def _overlap_seconds(a_start, a_end, b_start, b_end) -> int:
    """
    两个时间区间的交集秒数。
    右边的 a_end / b_end 可以是 None，表示"一直延续到现在"（用于正在播的段、本月边界）。
    """
    a_e = a_end or datetime.now()   # 正在播 → 算到此刻
    b_e = b_end or datetime.now()
    lo = max(a_start, b_start)
    hi = min(a_e, b_e)
    return max(0, int((hi - lo).total_seconds()))


def get_month_seconds(year: int, month: int, rids=None) -> int:
    """
    该月（可指定账号列表）的有效直播秒数。
    自动处理：跨天、跨月、正在播三种情况。
    注意：单场时长 < MIN_SESSION_SECONDS（默认 1 小时）的短场不计入。
    """
    start, nxt = month_bounds(year, month)
    with _connect() as conn:
        if rids:
            ph = ",".join("?" * len(rids))
            rows = conn.execute(
                f"SELECT rid, start_time, end_time, duration_seconds FROM sessions WHERE rid IN ({ph})", rids
            ).fetchall()
        else:
            rows = conn.execute("SELECT rid, start_time, end_time, duration_seconds FROM sessions").fetchall()

    total = 0
    for r in rows:
        s = _parse(r["start_time"])
        e = _parse(r["end_time"])
        dur = r["duration_seconds"]
        # 短场过滤：已下播且时长不足 1 小时的，不计入月度时长
        if dur is not None and dur < MIN_SESSION_SECONDS:
            continue
        if s is None or s >= nxt:
            continue                       # 开播在下月（或没时间），与本月无关
        if e is not None and e <= start:
            continue                       # 整段都在本月之前
        total += _overlap_seconds(s, e, start, nxt)
    return total


def format_hours(hours: float) -> str:
    """把小时数读成中国人习惯的 'X小时Y分'。"""
    total_min = round(hours * 60)
    h = total_min // 60
    m = total_min % 60
    return f"{h}小时{m}分" if h else f"{m}分"


def days_left_including_today(year: int, month: int) -> int:
    """
    本月剩余天数，【包含今天】。
    今天是第 d 天 → 还剩 (本月总天数 - d + 1) 天。
    如果统计的是过去的月份（不是当前月），返回 0（历史月份没有"剩余"概念）。
    """
    start, nxt = month_bounds(year, month)
    days_in_month = (nxt - start).days
    today = datetime.now()
    if (today.year, today.month) != (year, month):
        return 0
    return days_in_month - today.day + 1


def build_report(year: int, month: int, target_hours: float, rids=None) -> dict:
    """
    生成一份完整的月度报告字典。
    网页（第 5 步）和命令行都读这个字典，保证两边数字一致。
    """
    done_sec = get_month_seconds(year, month, rids)
    done_hours = done_sec / 3600
    target_sec = target_hours * 3600
    remain_sec = max(0, target_sec - done_sec)
    remain_hours = remain_sec / 3600
    is_current = (datetime.now().year, datetime.now().month) == (year, month)
    days_left = days_left_including_today(year, month)

    # 日均所需 = 剩余时长 / 剩余天数（含今日）。天数<=0 时给 0，避免除以零。
    daily_need_hours = (remain_sec / days_left / 3600) if days_left > 0 else 0.0

    return {
        "year": year,
        "month": month,
        "done_hours": round(done_hours, 2),
        "target_hours": target_hours,
        "remain_hours": round(remain_hours, 2),
        "is_current_month": is_current,
        "days_left": days_left,
        "daily_need_hours": round(daily_need_hours, 2),
        "progress_percent": round((done_hours / target_hours * 100), 1) if target_hours else 0.0,
    }


if __name__ == "__main__":
    # 自测：python src/analytics.py
    from database import init_db
    init_db()
    print(build_report(2026, 8, 156))
