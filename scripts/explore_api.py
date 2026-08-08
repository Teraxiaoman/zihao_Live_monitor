"""探测第三轮：测试 webcast enter 接口的返回结构。"""
import json
import sys
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

s = requests.Session()
s.headers.update({
    "User-Agent": UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://live.douyin.com/",
})
s.get("https://live.douyin.com/", timeout=15)
print("cookies:", list(s.cookies.keys()))

ENTER = "https://live.douyin.com/webcast/room/web/enter/"
BASE = {
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

rids = sys.argv[1:] or ["123456789", "745964462470"]
for rid in rids:
    p = dict(BASE, web_rid=rid)
    try:
        r = s.get(ENTER, params=p, timeout=15)
        print(f"\n=== web_rid={rid} HTTP {r.status_code} 长度 {len(r.text)} ===")
        try:
            d = r.json()
        except Exception:
            print("非 JSON:", r.text[:200]); continue
        print("status_code:", d.get("status_code"), "| msg:", d.get("status_msg", "")[:60])
        data = (d.get("data") or {})
        print("data 顶层键:", list(data.keys())[:15])
        rooms = data.get("data") or []
        if rooms:
            room = rooms[0]
            print("  room 键:", list(room.keys())[:20])
            print("  status =", room.get("status"))
            print("  title  =", room.get("title"))
            owner = room.get("owner") or {}
            print("  主播   =", owner.get("nickname"))
            st = room.get("stats") or {}
            print("  stats  =", {k: st[k] for k in list(st)[:5]})
        else:
            print("  无 room 数据；user 字段:", str(data.get("user"))[:200])
    except Exception as e:
        print(f"web_rid={rid} 出错: {e}")
