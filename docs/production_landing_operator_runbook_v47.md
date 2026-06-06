# v4.7 生产落地操作 Runbook

本文档用于排查并推进当前生产落地门禁。当前失败不是代码崩溃，而是门禁按预期阻止继续：`business_system` 尚未完成真实只读接入输入和真实 read smoke，人工签核仍保持 `No-Go`。

## 当前失败原因

- `production_landing_status.py` 输出 `status=partial`，表示只允许进入受控人工复核，不代表生产可上线。
- `execution_gate` 的 `blocked_domains` 当前应只包含 `business_system`；如果还包含 `real_llm`，优先重新运行小米 LLM 安全预检并刷新状态。
- `manual_signoff_evidence_ack_status` 仍为 `partial` 时，通常表示真实业务系统 read smoke 未完成、local mock 证据不能用于真实生产验收，或人工签核证据尚未完成。
- `manual_signoff.completed=false` 表示人工签核尚未完成。
- 本地 PostgreSQL、Redis、external MCP、business read smoke 可以形成 staging 证据，但不得包装为公网生产验收完成。

## 推荐执行顺序

1. 查看当前总状态：

   ```powershell
   python scripts/production_landing_status.py
   ```

2. 初始化或刷新本地落地环境模板：

   ```powershell
   python scripts/production_landing_env_init.py
   python scripts/production_landing_xiaomi_llm_bootstrap.py
   ```

3. 执行小米真实 LLM 安全预检。优先使用受控 runner：

   ```powershell
   python scripts/production_landing_env_runner.py --action xiaomi-llm-preflight
   ```

   如果 `XIAOMI_LLM_API_KEY` 已由外部 secret 管理注入到当前进程，也可以直接运行：

   ```powershell
   python scripts/production_landing_xiaomi_llm_preflight_runner.py --execute-network-check
   ```

   如果不希望在 shell 中设置密钥，使用交互式脚本：

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_preflight.ps1
   ```

   如果希望输入一次密钥后自动执行预检并刷新所有落地状态报告，使用恢复推进脚本：

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/xiaomi_llm_landing_resume.ps1
   ```

4. 刷新环境检查和执行门禁：

   ```powershell
   python scripts/production_landing_env_check.py
   python scripts/production_landing_execution_gate.py
   ```

5. 刷新本地 PostgreSQL、Redis、MCP smoke：

   ```powershell
   python scripts/production_landing_env_runner.py --action local-infra-mcp-smoke
   ```

6. 刷新业务系统只读 smoke：

   ```powershell
   python scripts/production_landing_env_runner.py --action local-business-smoke
   ```

   `local-business-smoke` 只用于本地演示，会生成 `local_business_mock_used=true` 的证据，不能作为真实业务系统验收。真实业务系统接入必须使用：

   ```powershell
   python scripts/production_landing_env_runner.py --action business-smoke
   ```

   更推荐使用安全 PowerShell 入口。它可以通过 `-EnvPath` 读取非密钥配置和 owner 标识，但会跳过 `BUSINESS_SYSTEM_BASE_URL`、`BUSINESS_SYSTEM_TOKEN` 等 secret 值；真实 URL/token 仍只来自当前进程环境或交互式输入：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\business_system_read_smoke.ps1 -EnvPath local\production_landing.staging.env
   ```

   通过 SSH tunnel、反向代理或 port-forward 暴露到 `localhost` 的真实业务系统不再自动判为 local mock；只有显式设置 `BUSINESS_SYSTEM_NAME=local_business_read_mock` 或运行 `local-business-smoke` 生成的证据才会标记 `local_business_mock_used=true`。local mock 证据不能作为真实业务系统验收。

7. 真实 LLM 预检成功后，执行受控 staging smoke：

   ```powershell
   python scripts/real_integration_staging_smoke.py --execute --domains real_llm,postgres,redis,external_mcp
   ```

8. 顺序刷新所有落地状态报告：

   ```powershell
   python scripts/production_landing_refresh_status.py --closure-evidence docs/reports/launch_blocker_closure/closure_evidence.draft.json
   ```

9. 重新生成证据确认状态：

   ```powershell
   python scripts/manual_signoff_evidence_ack_status.py
   ```

10. 查看下一步行动包：

   ```powershell
   python scripts/production_landing_action_pack.py
   ```

## 密钥处理边界

- 不把 API key 写入 `.env.example`、`.env.production.example`、报告、日志、Markdown 或命令行参数。
- 本地 `local/production_landing.staging.env` 已被 gitignore；即便如此，也优先使用外部 secret 管理或交互式进程环境注入。
- 交互式脚本必须使用 `Read-Host -AsSecureString` 接收密钥。
- 报告只输出 `api_key_present`、`network_check_executed`、`real_llm_executed` 等布尔字段，不输出 secret 原文。
- 不提交 `XIAOMI_LLM_API_KEY`、`DATABASE_URL`、`REDIS_URL`、业务系统 token 或 MCP command 中的 secret。

## 完成判定

- `production_landing_xiaomi_llm_preflight` 最新报告为 `status=success`。
- 最新报告中 `network_check_executed=true` 且 `real_llm_executed=true`。
- `production_landing_execution_gate` 不再阻断 `real_llm`。
- PostgreSQL、Redis、external MCP、business system read smoke 当前轮证据为 `success`。
- `manual_signoff_evidence_ack_status` 的 `recommended_accept_count=4/4`。
- 人工签核记录由 release、security、business、operations 四类负责人完成，且 `public_production_direct_launch=No-Go` 仍保持。

## 不允许的结论

- 不宣称公网生产可直接上线。
- 不宣称真实 LLM、PostgreSQL、Redis、external MCP 或业务系统生产验收已完成，除非当前轮结构化证据明确证明。
- 不绕过 ToolGateway、PolicyEngine、审批链路或审计链路。
