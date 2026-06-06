# v4.5 小米 OpenAI-compatible LLM 接入说明

## 定位

本项目通过既有 `LiteLLMProvider` 接入 OpenAI-compatible LLM 服务。小米提供的 OpenAI-compatible URL 通过 `REAL_LLM_BASE_URL` 接入，密钥只通过本地受控环境变量注入，不写入仓库、报告、日志、Markdown 或审计导出原文。

## 必需配置

本轮已确认的 provider 配置：

```powershell
$env:REAL_LLM_ACCEPTANCE_ENABLED="true"
$env:REAL_LLM_PREFLIGHT_ENABLED="true"
$env:REAL_LLM_PROVIDER="litellm"
$env:REAL_LLM_MODEL="mimo-v2.5-pro"
$env:REAL_LLM_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
$env:REAL_LLM_API_KEY_ENV="XIAOMI_LLM_API_KEY"
$env:REAL_LLM_PREFLIGHT_NETWORK_CHECK="true"
```

密钥必须通过进程环境或交互式安全输入注入：

```powershell
$env:XIAOMI_LLM_API_KEY="<external-secret-managed-token>"
python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check
```

如果不希望在命令行或 shell 历史中设置密钥，使用交互式安全脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1
```

该脚本使用 `Read-Host -AsSecureString`，只在当前 PowerShell 子进程内临时设置 `XIAOMI_LLM_API_KEY`，结束后恢复进程环境。

## 进入受控 staging smoke

真实 LLM preflight 成功后，再执行受控真实集成 smoke：

```powershell
python scripts/production_landing_env_check.py
python scripts/production_landing_execution_gate.py
python scripts/real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp
```

## 当前边界

- 默认 fake/offline 路径保持不变，默认测试不调用真实 LLM。
- 真实 LLM smoke 只代表 staging 证据进入人工复核，不代表公网生产验收完成。
- 报告只允许输出 `api_key_present`、`network_check_executed`、`real_llm_executed` 等布尔字段。
- 禁止提交 API key、token、连接串密码或任何 secret 原文。
- `public_production_direct_launch` 必须保持 `No-Go`，除非后续有正式生产发布审批。
