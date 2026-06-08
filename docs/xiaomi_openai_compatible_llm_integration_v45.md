# v4.5 OpenAI-compatible LLM 接入说明

## 定位

项目通过现有 `LiteLLMProvider` 接入 OpenAI-compatible LLM 服务。当前默认落地入口使用通用 `REAL_LLM_*` 配置，模型可配置为 `gpt-5.5`，小米 `mimo-v2.5-pro` 入口继续作为兼容路径保留。

密钥只允许通过当前进程环境、外部 secret manager 或交互式安全输入注入；不得写入仓库、报告、日志、Markdown 或审计导出原文。

## 通用配置

```powershell
$env:REAL_LLM_ACCEPTANCE_ENABLED="true"
$env:REAL_LLM_PREFLIGHT_ENABLED="true"
$env:REAL_LLM_PROVIDER="litellm"
$env:REAL_LLM_MODEL="gpt-5.5"
$env:REAL_LLM_BASE_URL="http://100.119.206.22:8300/v1"
$env:REAL_LLM_API_KEY_ENV="REAL_LLM_API_KEY"
$env:REAL_LLM_PREFLIGHT_NETWORK_CHECK="true"
```

推荐使用交互式安全脚本执行真实 preflight：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\real_llm_preflight.ps1
```

脚本使用 `Read-Host -AsSecureString`，只在当前 PowerShell 子进程内临时设置 `REAL_LLM_API_KEY`，结束后恢复进程环境。

## 小米兼容路径

如需继续使用小米兼容服务，可执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\xiaomi_llm_preflight.ps1
```

## 进入受控 staging smoke

真实 LLM preflight 成功后，再执行受控真实集成 smoke：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_env_check.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\production_landing_execution_gate.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp
```

## 当前边界

- 默认 fake/offline 路径保持不变，默认测试不调用真实 LLM。
- 真实 LLM smoke 只代表 staging 证据进入人工复核，不代表公网生产验收完成。
- 报告只允许输出 `api_key_present`、`network_check_executed`、`real_llm_executed` 等布尔字段。
- 禁止提交 API key、token、连接串密码或任何 secret 原文。
- `public_production_direct_launch` 必须保持 `No-Go`，除非后续有正式生产发布审批。
