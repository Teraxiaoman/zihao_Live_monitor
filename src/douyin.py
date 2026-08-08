"""
抖音直播状态查询模块。

只做一件事：给一个抖音号，告诉你这个人现在是不是在直播。

原理说明（这段值得读）：
    抖音网页版打开一个直播间时，浏览器会偷偷向
    https://live.douyin.com/webcast/room/web/enter/ 发一个请求，
    服务器返回这个直播间的全部信息（是否在播、标题、人数……）。
    我们要做的就是模仿浏览器发同样的请求。

    唯一的门槛是：抖音要求请求里带一个叫 ttwid 的 cookie。
    这个 cookie 只要访问一次抖音首页就会自动拿到，不需要登录。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import requests

# 伪装成 Chrome 浏览器。不加这个，抖音会认出你是脚本并拒绝。
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

ENTER_URL = "https://live.douyin.com/webcast/room/web/enter/"

# 这一堆参数是浏览器真实发送的，照抄即可，不用背
_BASE_PARAMS = {
    "aid": "6383",
    "app_name": "douyin_web",
    "live_id": "1",
    "device_platform": "web",
    "language": "zh-CN",
    "enter_from": "web_live",
    "cookie_enabled": "true",
    "screen_width": "1920",
    "screen_height": "1080",
    "browser_language": "zh-CN",
    "browser_platform": "Win32",
    "browser_name": "Chrome",
    "browser_version": "131.0.0.0",
}


@dataclass
class LiveStatus:
    """一次查询的结果。用 dataclass 而不是字典，好处是拼错字段名会立刻报错。"""

    rid: str                      # 抖音号
    ok: bool = False              # 这次查询本身是否成功（网络/接口层面）
    is_living: bool = False       # 是否正在直播
    nickname: str = ""            # 主播昵称
    title: str = ""               # 直播间标题
    user_count: str = ""          # 在线人数（抖音给的是字符串，如 "1.2万"）
    error: str = ""               # 查询失败时的原因
    raw: dict = field(default_factory=dict, repr=False)  # 原始数据，排错用

    def describe(self) -> str:
        """给人看的一句话描述。"""
        if not self.ok:
            return f"[{self.rid}] 查询失败：{self.error}"
        who = self.nickname or self.rid
        if self.is_living:
            return f"[{who}] 🔴 正在直播 | {self.title} | 在线 {self.user_count}"
        return f"[{who}] ⚪ 未开播"


def create_session() -> requests.Session:
    """
    创建一个"会话"并预热。

    Session 的作用是自动保存 cookie，这样第一次访问首页拿到的 ttwid
    会被记住，后面的请求自动带上。如果每次都用 requests.get()，
    cookie 就丢了，抖音会拒绝你。
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://live.douyin.com/",
    })
    try:
        # 访问首页，目的只是让抖音给我们种下 ttwid cookie
        session.get("https://live.douyin.com/", timeout=15)
    except requests.RequestException:
        # 预热失败不致命，后面请求可能仍然成功，所以不抛异常
        pass
    return session


def fetch_live_status(rid: str, session: Optional[requests.Session] = None) -> LiveStatus:
    """
    查询一个抖音号当前的直播状态。

    参数:
        rid: 抖音号（就是直播间链接 live.douyin.com/后面那串数字）
        session: 可选，复用已有会话可以省掉预热请求

    返回:
        LiveStatus 对象。注意：即使查询失败也会正常返回（ok=False），
        不会抛异常。因为这个函数会在循环里每分钟跑一次，
        一次网络抖动就让整个程序崩掉是不可接受的。
    """
    rid = str(rid).strip()
    result = LiveStatus(rid=rid)

    if not rid:
        result.error = "抖音号为空"
        return result

    if session is None:
        session = create_session()

    params = dict(_BASE_PARAMS, web_rid=rid)

    try:
        resp = session.get(ENTER_URL, params=params, timeout=15)
    except requests.RequestException as exc:
        result.error = f"网络请求失败: {exc}"
        return result

    if resp.status_code != 200:
        result.error = f"HTTP {resp.status_code}（可能被风控了，稍后再试）"
        return result

    try:
        payload = resp.json()
    except ValueError:
        result.error = "返回的不是 JSON，抖音接口可能改版了"
        return result

    if payload.get("status_code") != 0:
        result.error = f"抖音返回错误: {payload.get('status_msg', '未知')}"
        return result

    data = payload.get("data") or {}
    result.raw = data
    result.ok = True

    # 主播信息在 data.user 里，即使没开播也有
    user = data.get("user") or {}
    result.nickname = user.get("nickname", "")

    # 直播间信息在 data.data 列表里，没开播时这个列表可能是空的
    rooms = data.get("data") or []
    room = rooms[0] if rooms else {}

    # 判断是否在播：用两个字段互相印证，任一命中就算在播。
    # room_status: 0=在播, 2=不在播
    # status:      2=在播, 4=已结束
    # 为什么要双保险？因为抖音偶尔只更新其中一个字段。
    room_status = data.get("room_status")
    status = room.get("status")
    result.is_living = (room_status == 0) or (status == 2)

    result.title = room.get("title", "")
    result.user_count = room.get("user_count_str", "")

    return result


if __name__ == "__main__":
    # 直接运行本文件时的自测：python src/douyin.py 抖音号
    import sys

    test_rid = sys.argv[1] if len(sys.argv) > 1 else "745964462470"
    print(fetch_live_status(test_rid).describe())
