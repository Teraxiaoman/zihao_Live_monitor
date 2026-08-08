# 子浩先生开播了么 · 抖音开播监测

监测抖音主播（大号 / 小号）的开播状态，开播 / 下播时通过 **Server酱** 推送微信提醒，
记录每段直播起止时间，计算当月累计时长、与目标差距、剩余日均；并提供手机网页看板。

> 对应需求：「类似『陈泽开播了么』的小工具」——监测开播、微信提醒、时长统计、目标差距。

## 功能

- 🔴 双账号监测：大号 `Zihaolaoshi.`、小号 `zihaolaoshi`（抖音号在 `config.json` / 云端环境变量配置）
- 📲 微信推送：开播 / 下播时推 Server酱 模板消息，可在看板里一键开关「实时推送」
- 🗓️ 时长统计：按月累计、跨天 / 跨月自动拆分、不足 1 小时的短场不计入
- 🎯 目标差距：默认每月 156 小时，显示已播 / 剩余 / 剩余日均（剩余天数含当日）
- 📱 手机看板：莫兰迪雾蓝风格，双 Tab（直播状态 / 时长记录），支持自定义头像、历史记录手动校正
- ☁️ 7×24 运行：部署到 GitHub Actions 定时监测 + GitHub Pages 托管看板（详见第 6 步）

## 目录结构

```
zhibo/
├── config.example.json     配置模板（复制成 config.json 再填）
├── config.json             你的真实配置（含密钥，**不会**上传 GitHub，已被 .gitignore 忽略）
├── requirements.txt        依赖清单
├── monitor.py              监测主程序（单次 / 循环 / 测试推送 / 报告）
├── gen_data.py             生成看板数据 docs/data.json + data.js
├── serve.py                本地可写服务器（看板 + 历史记录校正接口），端口 8777
├── src/
│   ├── douyin.py           核心：抖音开播状态查询（需先拿 ttwid cookie）
│   ├── notify.py           Server酱 微信推送
│   ├── database.py         SQLite 直播场次记录
│   ├── analytics.py        时长统计与目标差距
│   └── push_state.py       推送开关状态（开关持久化到 data/push_state.json）
├── scripts/
│   ├── backfill.py         历史数据回填（手动校正用）
│   └── explore_api.py      接口探索工具（学习用）
├── docs/
│   ├── index.html          手机看板页面
│   ├── data.json           看板数据（由 gen_data.py 生成，会被 GitHub Pages 托管）
│   └── data.js             离线兜底数据
├── data/                   运行数据（live_sessions.db / state.json / push_state.json，会上传用于云端持久化）
└── .github/workflows/      GitHub Actions 定时监测工作流
```

## 本地使用（自测 / 开发）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置账号（本地）

把 `config.example.json` 复制为 `config.json`，填入你的账号与 Server酱 SendKey：

```json
{
  "accounts": [
    {"name": "子浩.", "rid": "Zihaolaoshi.", "avatar": ""},
    {"name": "子浩（沉淀版）.", "rid": "zihaolaoshi", "avatar": ""}
  ],
  "monthly_target_hours": 156,
  "serverchan_key": "SCTxxxxxxxxxxxxxxxxxxxxxxxx"
}
```

> `config.json` 含密钥，已被 `.gitignore` 忽略，绝不会上传到 GitHub。
> 云端部署时不需要这个文件，账号与目标改由 GitHub 环境变量提供（见第 6 步）。

### 3. 跑起来

```bash
python monitor.py --once       # 查一次状态（演练：加 MONITOR_DRYRUN=1 不真发微信）
python monitor.py --test-push  # 发一条测试微信，确认推送通不通
python monitor.py --report     # 打印本月时长 / 距目标 / 日均报告
python serve.py                # 启动看板（http://127.0.0.1:8777/）
```

看板通过 `http://127.0.0.1:8777/` 访问（**必须走这个地址**，编辑按钮、推送开关才可用；
直接双击 html 文件以 `file://` 打开时这些功能不可用）。

## 第 6 步：部署到 GitHub（7×24 自动运行 + 手机看板）

目标：GitHub Actions 每 10 分钟跑一次 `monitor.py`，检测到开播 / 下播推微信；
`gen_data.py` 生成的最新看板数据由 **GitHub Pages** 托管，手机随时看。

> 本仓库已写好 `.github/workflows/monitor.yml`，你只需在 GitHub 上做几步配置。

### 方式 A：GitHub Desktop（最简单，推荐小白）

1. 去 https://github.com 注册一个**免费**账号。
2. 下载安装 **GitHub Desktop**：https://desktop.github.com/
3. 打开 GitHub Desktop，登录你的账号。
4. `File → Add Local Repository`，选择本机目录 `D:/ps/zhls/zhibo`。
5. 点 `Publish repository`：
   - Name 填 `zihao-live-monitor`（或任意）
   - **Visibility 选 Public（公开）**
   - 不要勾「Keep this code private」的相反——即保持 Public
   - 点 Publish
6. 跳到下方「配置 Secret」和「开启 Pages」。

### 方式 B：命令行 + Personal Access Token（PAT）

1. 去 https://github.com 注册账号，新建一个**公开**空仓库（不要勾 README / .gitignore）。
2. 生成 PAT：GitHub 右上角头像 → Settings → Developer settings →
   Personal access tokens → Tokens (classic) → Generate new token，
   勾 `repo` 权限，生成后**复制保存**（只显示一次）。
3. 在本机命令行：

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
# 用户名填你的 GitHub 账号，密码处粘贴上面生成的 PAT
```

### 配置 Secret（推送密钥，安全存储）

1. 进入你的仓库 → `Settings → Secrets and variables → Actions`。
2. 点 `New repository secret`：
   - **Name**：`SERVERCHAN_KEY`
   - **Secret**：`SCT393050TagDsteA1HoC7jy3Xn2wJIP3J`（你的 SendKey）
3. 保存。代码里只会引用 `${{ secrets.SERVERCHAN_KEY }}`，SendKey 不会进代码。

### 开启 Pages（托管看板）

1. 仓库 → `Settings → Pages`。
2. Source 选 `Deploy from a branch`。
3. Branch 选 `main`，文件夹选 `/docs`。
4. 点 Save。
5. 几分钟后访问 `https://<你的用户名>.github.io/<仓库名>/` 即可看到看板。

### 触发与验证

- Actions 默认每 5 分钟自动跑。首次可手动触发：仓库 `Actions` 标签 →
  选「子浩开播监测」→ `Run workflow`。
- 看板数据每次运行后自动更新（workflow 会把 `data/live_sessions.db`、`docs/data.json` 等
  推回仓库，实现云端持久化，不会重复记开播）。
- 在手机微信里让「子浩」开播一次，应收到 Server酱 推送；看板状态变「直播中」。

## 安全与隐私

- **SendKey 安全**：仅存于 GitHub Secrets，绝不进代码 / 仓库。
- **公开仓库说明**：你选了公开仓库，Actions 免费额度无限（私有仓库仅 2000 分钟/月，跑 10 分钟
  一次的监测会超额停摆）。公开意味着被追踪的 `data/live_sessions.db`（开播/下播时间记录）也对外可见。
  若介意，可改用私有仓库并把监测频率调低（如每 30 分钟一次）。
- **密钥文件**：`config.json` 已被 `.gitignore` 忽略，上传前会自动排除。

## 常见问题

- **看板编辑按钮 / 推送开关点不了？** 必须通过 `http://127.0.0.1:8777/` 访问；双击 html 以
  `file://` 打开时后端不可用，这些功能会隐藏。云上通过 Pages 访问时同理由 GitHub 后端保障。
- **抖音查不到状态？** 首次需访问一次 `live.douyin.com` 拿到 `ttwid` cookie，`douyin.py` 会自动处理。
- **短场不计入时长？** 单场不足 1 小时（`MIN_SESSION_SECONDS=3600`）不会计入月度统计，但数据库保留记录。
- **剩余天数含当日？** 公式：`本月天数 - 今天 + 1`，例如 8 月 8 日 → 31-8+1=24 天。
