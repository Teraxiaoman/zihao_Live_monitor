"""
本地可写服务器：既能托管看板页面，又能接收"编辑校正"请求写进数据库。

为什么需要它：
    看板页面(dashboard/index.html)是纯静态的，只能读数据。
    但"历史记录校正"要修改数据库里的开播/下播时间，必须有后端写接口。
    这个服务器用 Python 标准库实现，不用 pip 安装任何东西。

用法（在你的电脑上跑，编辑功能就可用）：
    python serve.py                 # 默认 http://127.0.0.1:8777/
    python serve.py --port 9000     # 换端口

接口：
    GET  /api/health                -> {"ok": true}        前端用来判断"能否编辑"
    POST /api/update_session        -> 改一条记录的起止时间，并重算时长、刷新看板
    其余路径                        -> 当作静态文件，托管 dashboard/ 目录

说明：编辑必须在"本机这个服务器"下进行（数据文件在你电脑上）。
      改完之后，dashboard/data.json 会自动重生成，发布到云上就是校正后的数据。
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))
DASHBOARD_DIR = ROOT / "dashboard"

from database import init_db, _connect          # noqa: E402
import gen_data                                 # noqa: E402
from push_state import is_enabled, set_enabled, toggle  # noqa: E402

FMT = "%Y-%m-%d %H:%M:%S"


def _update_session(sid, start, end):
    """改数据库里某条记录的起止时间，重算时长。end 为空表示仍在播(进行中)。"""
    init_db()
    with _connect() as conn:
        if end:
            try:
                secs = max(0, int((datetime.strptime(end, FMT) - datetime.strptime(start, FMT)).total_seconds()))
            except ValueError:
                secs = 0
            conn.execute(
                "UPDATE sessions SET start_time=?, end_time=?, duration_seconds=? WHERE id=?",
                (start, end, secs, sid),
            )
        else:
            conn.execute(
                "UPDATE sessions SET start_time=?, end_time=NULL, duration_seconds=NULL WHERE id=?",
                (start, sid),
            )


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(DASHBOARD_DIR), **k)

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/health"):
            return self._json({"ok": True})
        if self.path.startswith("/api/push_status"):
            return self._json({"ok": True, "enabled": is_enabled()})
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/update_session"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                sid = int(body["id"])
                start = str(body["start_time"]).strip()
                end = (body.get("end_time") or "").strip()
                _update_session(sid, start, end or None)
                gen_data.main()          # 改完立刻重生成 data.json / data.js，看板自动更新
                return self._json({"ok": True})
            except Exception as e:
                traceback.print_exc()
                return self._json({"ok": False, "error": str(e)}, code=400)
        if self.path.startswith("/api/push_toggle"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                # 如果请求体显式传了 enabled，就按请求体设置；否则翻转
                if "enabled" in body:
                    set_enabled(bool(body["enabled"]))
                else:
                    toggle()
                return self._json({"ok": True, "enabled": is_enabled()})
            except Exception as e:
                traceback.print_exc()
                return self._json({"ok": False, "error": str(e)}, code=400)
        self.send_error(404)

    def log_message(self, fmt, *args):
        pass   # 安静一点，不刷屏


def main() -> None:
    port = 8777
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])
    init_db()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"看板可写服务器已启动： http://127.0.0.1:{port}/")
    print("（编辑校正功能需通过此地址访问；Ctrl+C 停止）")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
