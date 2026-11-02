# SWU 学工系统自动打卡

一个完整的多账号打卡控制台：使用办事大厅账号、密码和验证码登录 IDM，经
UAAAP/CAS 建立 eHall 会话，再查询或提交新生打卡。项目不依赖钉钉登录状态，
包含独立的管理前端、API、任务队列、定时执行与飞书汇总。

> 仅用于账号本人知情并授权的正常打卡。请遵守学校规定，并自行确认自动化运行
> 是否符合当前管理要求。

## 功能

- 每天 21:05（Asia/Shanghai）为全部启用账号串行执行。
- 自动失败后等待 10 秒，以全新的浏览器会话重试一次；不做长时间循环重试。
- 管理员可直接添加/修改账号密码，也可发送一次性邀请链接让对方填写。
- 管理员可手动执行单个账号、全部账号或重试失败账号。
- 邀请链接默认 24 小时有效，被邀请人无需注册。
- 飞书机器人接收每日成功/失败汇总。
- 前端不高频轮询，只在操作后延迟刷新一次、窗口重新获得焦点或手动刷新时更新。

## 架构

```text
Cloudflare Pages (checkin.example.com)
              │ HTTPS + Secure HttpOnly Cookie
              ▼
Cloudflare Tunnel (api-checkin.example.com)
              │ 127.0.0.1:8765
              ▼
FastAPI ── SQLite (WAL)
              │
              ▼
串行 Worker ── Chrome / Xvfb ── SWU eHall
```

学校账号、密码、飞书 Webhook 与签名密钥使用 AES-256-GCM 加密；主密钥只保留
在服务器 Credential 文件中。管理员密码使用 Argon2id，登录使用 Secure、
HttpOnly Cookie 和 CSRF 校验。API 永远不会返回已保存凭据。

## 本地开发

需要 Python 3.11+、Node.js 22+ 和 Google Chrome。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:APP_MASTER_KEY = python -m server.cli generate-key
$env:APP_ENV = "development"
$env:DATABASE_URL = "sqlite:///./data/checkin.db"
$env:FRONTEND_ORIGIN = "http://localhost:5173"
python -m server.cli init-db
python -m server.cli create-admin admin
```

分别启动 API、Worker 和前端：

```powershell
python -m uvicorn server.asgi:app --host 127.0.0.1 --port 8000
python -m server.worker
cd frontend
npm install
npm run dev
```

原单账号命令行仍可独立使用：

```powershell
Copy-Item .env.example .env
python -m freshman_checkin --status-only
python -m freshman_checkin
```

## 服务器部署

推荐 Ubuntu 与 Cloudflare Tunnel。安装脚本会通过 Playwright 下载与服务器架构
匹配的 Chrome for Testing，无需 Snap；12 GB 内存足够，Worker 默认始终只执行
一个 Chrome 任务。在 Ubuntu 24.04 上，安装脚本还会为该浏览器加载定向
AppArmor `userns` 规则，保留 Chromium 沙箱而不修改系统全局安全设置。

1. 把仓库放到服务器后执行 `sudo bash deploy/install-server.sh`。
2. 编辑 `/etc/check-new/check-new.env`，至少修改前端域名；浏览器路径已固定为
   `/opt/check-new/chrome`。
3. 首次创建管理员（主密钥文件不会显示到命令行）：

```bash
sudo -u check-new env \
  APP_ENV=production \
  APP_MASTER_KEY_FILE=/etc/check-new/app_master_key \
  DATABASE_URL=sqlite:////var/lib/check-new/checkin.db \
  FRONTEND_ORIGIN=https://checkin.example.com \
  /opt/check-new/venv/bin/python -m server.cli create-admin admin
```

4. 启动并设为开机运行：

```bash
sudo systemctl enable --now check-new-api.service
sudo systemctl enable --now check-new-worker.service
sudo systemctl enable --now check-new-scheduler.timer
systemctl list-timers check-new-scheduler.timer
curl http://127.0.0.1:8765/api/health
```

5. 按 [Cloudflare 部署说明](deploy/cloudflared/README.md)给现有 Tunnel 新增 API
   hostname，并把 `frontend` 目录连接到 Cloudflare Pages。

### 更新

更新代码后重新运行安装脚本，再重启两个常驻服务：

```bash
sudo bash deploy/install-server.sh
sudo systemctl restart check-new-api check-new-worker
```

### 备份与恢复

先停止 Worker，再用 SQLite 在线备份命令创建一致快照：

```bash
sudo systemctl stop check-new-worker
sudo -u check-new sqlite3 /var/lib/check-new/checkin.db \
  ".backup '/var/lib/check-new/checkin-backup.db'"
sudo systemctl start check-new-worker
```

同时离线保存 `/etc/check-new/app_master_key`；没有原主密钥就无法解密备份中的账号。
恢复时停止 API/Worker，用备份替换数据库后保持所有者为 `check-new:check-new`，再
启动服务。不要把数据库或主密钥提交到 Git。

## 测试

```powershell
python -m compileall -q freshman_checkin server tests
python -m unittest discover -s tests -v
cd frontend
npm run build
npm audit --audit-level=high
```

状态查询和提交仍遵循后端下发的 `IN_TIME` 与 `HAS_QD`。默认不使用 `--force`，
代码使用后端下发的地点配置构造请求，不读取设备 GPS。
