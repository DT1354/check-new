# swu学工系统自动打卡

使用办事大厅账号、密码和验证码登录 IDM，经 UAAAP/CAS 建立 eHall 会话，
再查询或提交打卡。认证、浏览器安全验证、状态查询和提交逻辑都包含在
本仓库中，不依赖钉钉登录状态。

> 仅用于本人账号的正常打卡。请遵守学校规定，并自行确认自动化运行是否符合
> 当前管理要求。

## 工作流程

1. 使用账号、密码和 OCR 验证码登录 IDM。
2. 在完整 Chrome 图形引擎中完成 UAAAP/CAS 与 eHall 安全验证。
3. 初始化新生应用的学生角色并调用 `getKqInfo.do` 查询当天状态。
4. 已打卡时直接退出；未打卡时按后端 `IN_TIME` 标记决定是否提交。
5. 调用 `addKqInfo.do` 后再次查询，确认 `HAS_QD=1` 才报告成功。

代码使用后端下发的打卡地点配置构造请求，不读取设备 GPS。它不会打印账号、
密码、CAS ticket、Cookie、学号或精确坐标。

## 本地运行

需要 Python 3.11+ 和 Google Chrome。（浏览器）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写自己的账号和密码：

```text
SWU_USERNAME=你的账号
SWU_PASSWORD=你的密码
```

只查询，不提交：

```powershell
python -m freshman_checkin --status-only
```

正常执行：

```powershell
python -m freshman_checkin
```

默认模式会启动系统 Chrome 的完整图形引擎并将窗口移到屏幕外，以通过 eHall
安全验证。找不到 Chrome 时可设置 `CHROME_PATH`。

## 部署

-部署时只使用仓库 Secrets：`SWU_USERNAME` 和 `SWU_PASSWORD`。
- `--force` 会忽略后端时间标记，默认不会使用；自动化任务也不应默认开启。


## 测试

```powershell
python -m compileall -q freshman_checkin tests
python -m unittest discover -s tests -v
```
