"""
第 1 步的运行入口：查一次直播状态，打印出来。

用法（两种都行）：
    python check_once.py 抖音号            <- 临时查某个号，不用改配置
    python check_once.py                   <- 查 config.json 里配置的所有号
"""
import json
import sys
from pathlib import Path

# 让 Python 能找到 src 目录里的模块
sys.path.insert(0, str(Path(__file__).parent / "src"))

from douyin import create_session, fetch_live_status  # noqa: E402

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_accounts() -> list[dict]:
    """从 config.json 读要监测的账号列表。"""
    if not CONFIG_PATH.exists():
        print("找不到 config.json。")
        print("请把 config.example.json 复制一份改名为 config.json，")
        print("然后把里面的抖音号换成真实的。")
        return []

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    accounts = config.get("accounts", [])
    # 过滤掉还没填的示例数据，避免白跑一趟
    return [a for a in accounts if a.get("rid") and not str(a["rid"]).startswith("这里填")]


def main() -> None:
    # 只创建一个 session 反复使用：省掉重复预热，也更像真实浏览器
    session = create_session()

    if len(sys.argv) > 1:
        accounts = [{"name": f"命令行指定({rid})", "rid": rid} for rid in sys.argv[1:]]
    else:
        accounts = load_accounts()

    if not accounts:
        print("\n没有要查询的账号。先填 config.json，或者直接：python check_once.py 抖音号")
        return

    print(f"开始查询 {len(accounts)} 个账号……\n")
    for acc in accounts:
        status = fetch_live_status(acc["rid"], session=session)
        label = acc.get("name", acc["rid"])
        print(f"{label:16s} {status.describe()}")


if __name__ == "__main__":
    main()
