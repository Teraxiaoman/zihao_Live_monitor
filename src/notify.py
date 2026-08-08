"""
微信推送模块（基于 Server酱 / SCT）。

Server酱是什么：一个免费服务，把你发的消息通过微信服务号推到你手机。
申请地址：https://sct.ftqq.com （扫码微信即送 SendKey，形如 SCTabc123...）

用法：
    from notify import push
    push("标题", "正文（支持 Markdown）", sendkey="SCTxxxx")

如果没填 sendkey，会自动进入"演练模式"：只打印、不真发，方便你先跑通逻辑。
"""
from __future__ import annotations

import requests

# Server酱 Turbo 版接口。老版是 sc.ftqq.com，这里用新版，更稳定。
_SCT_URL = "https://sctapi.ftqq.com/{key}.send"

# 超时设短一点：推送失败绝不能卡住主监测循环
_TIMEOUT = 10


def push(title: str, content: str = "", sendkey: str = "") -> bool:
    """
    发送一条微信消息。

    返回 True 表示发送成功（或演练模式下成功打印）。
    """
    if not sendkey:
        # 演练模式：不联网，只把内容打印出来，方便调试
        print("\n[推送-演练] " + "=" * 20)
        print("标题:", title)
        if content:
            print(content)
        print("=" * 28 + "\n")
        return True

    url = _SCT_URL.format(key=sendkey)
    try:
        resp = requests.post(
            url,
            data={"title": title, "desp": content},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"[推送-失败] 网络错误: {exc}")
        return False

    try:
        result = resp.json()
    except ValueError:
        print(f"[推送-失败] 返回异常 (HTTP {resp.status_code})")
        return False

    # Server酱成功时 code == 0
    if result.get("code") == 0:
        print(f"[推送-成功] {title}")
        return True
    else:
        print(f"[推送-失败] {result.get('message', '未知错误')} (code={result.get('code')})")
        return False


if __name__ == "__main__":
    # 自测：python src/notify.py
    push("✅ 推送测试", "如果你在微信收到这条，说明配置 OK", sendkey="")
