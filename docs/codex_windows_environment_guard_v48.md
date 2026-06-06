# v4.8 Codex Windows 环境稳定执行规范

本文用于降低 Windows PowerShell 5.1、中文路径、Python 解析、Git 用户目录权限和沙箱写入边界造成的重复失败。

## 已确认问题

- 默认 `python` 可能命中 Microsoft Store alias，导致脚本无法启动。
- Codex bundled Python 位于中文路径 `D:\codex*\tools\Python312\python.exe`，未统一解析时容易出现创建进程失败。
- Windows PowerShell 5.1 默认文件读取编码不是 UTF-8，直接 `Get-Content ... | ConvertFrom-Json` 读取中文 JSON 报告时会把内容读坏。
- Git 默认尝试读取 `C:\Users\Administrator\.config\git\ignore`，当前权限不足时会产生噪声。
- 通用 PowerShell wrapper 对 `-m`、`-q`、`-c` 这类 Python 参数不可隐式转发，必须使用专用 wrapper 或显式参数数组。

## 后续执行约定

优先使用专用入口：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 -m pytest tests/test_codex_env_guard_v487.py -q
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_status.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_git.ps1 status --short
```

需要检查当前环境时使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_env_guard.ps1 -CheckOnly
```

仍需使用通用 guard 时，对带短横线的参数使用显式数组：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_env_guard.ps1 -Command python -Arguments @('-m','pytest','tests/test_codex_env_guard_v487.py','-q')
```

读取 UTF-8 JSON/Markdown 报告时必须显式指定编码：

```powershell
$payload = Get-Content -LiteralPath 'docs\reports\example\report.json' -Encoding UTF8 -Raw | ConvertFrom-Json
$markdown = Get-Content -LiteralPath 'docs\reports\example\report.md' -Encoding UTF8 -Raw
```

不要使用：

```powershell
Get-Content -LiteralPath 'docs\reports\example\report.json' -Raw | ConvertFrom-Json
```

## 包装器行为

- 统一设置控制台输入输出为 UTF-8。
- 统一设置 `XDG_CONFIG_HOME` 到仓库内 `.git-xdg`，避免访问用户目录 Git 配置。
- 统一设置 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`。
- Python 优先解析非 WindowsApps 的 `python.exe`，其次查找 `D:\codex*\tools\Python312\python.exe`，最后才使用 `py -3`。
- `.git-xdg/` 与 `.codex-env/` 已加入 `.gitignore`，不得提交本地状态。

## 安全边界

- 不在 wrapper、文档、报告或命令行中写入 API key、token、连接串密码或其他 secret 原文。
- 小米 LLM API key 仍只能通过进程环境或交互式 `Read-Host -AsSecureString` 注入。
- 真实 LLM、PostgreSQL、Redis、MCP 和业务系统仍保持 opt-in，不因环境 wrapper 自动执行真实连接。
- `public_production_direct_launch` 继续保持 `No-Go`，环境稳定不等于生产上线批准。
