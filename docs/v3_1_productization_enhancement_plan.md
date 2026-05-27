# v3.1 Productization Enhancement 规划

## 1. 阶段定位

- v3.1 定位：**Productization Enhancement**。
- 面向企业内网试点后的产品可用性、观测性、演示闭环与运维体验增强。
- 不改变 v3.0.0 已发布事实，不移动/删除/重建任何既有 tag（含 `v3.0.0`）。

## 2. 当前能力基线

- v2.7：Production Security Baseline（安全基线）
- v2.8：Controlled Real LLM Pilot（受控试点入口）
- v2.9：Real LLM Controlled Pilot Evidence（受控试点证据闭环）
- v3.0：Final Production Landing（企业内网试点/准生产演示落地）

## 3. 建议 Phase 与执行要点

### Phase 11.1：演示数据与端到端演示脚本（P0）

- 目标：
  - 提升产品演示可重复性与“一键演示”效率。
- 修改范围：
  - `docs/` 演示流程文档、`scripts/` 演示脚本、必要的示例数据模板（脱敏/非生产数据）。
- 不做什么：
  - 不引入真实外网 LLM 默认调用；
  - 不改核心业务逻辑与权限模型。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
  - 演示脚本 smoke（如 `scripts/demo_*.ps1`）
- 完成标准：
  - 在新环境按文档可复现演示流程；
  - 演示脚本有明确输入/输出与失败处理说明。

当前状态（2026-05-27）：

- 已落地：
  - `scripts/demo_seed_data.py`
  - `scripts/demo_e2e.ps1`
  - `docs/demo_e2e_runbook_v31.md`
- 已补充最小测试：`tests/test_demo_seed_data_v311.py`

### Phase 11.2：只读运营总览 Dashboard（P0）

- 目标：
  - 汇总 health/metrics/audit/pilot reports 只读视图，降低验收沟通成本。
- 修改范围：
  - 前端只读页面与后端已有只读 API 聚合展示（不新增敏感写操作）。
- 不做什么：
  - 不增加执行真实 LLM 按钮；
  - 不新增密钥录入入口。
- 验证命令：
  - `python -m pytest tests/test_llm_pilot_reports_v94.py -q`
  - `python -m pytest tests/test_audit_retention_export_v74.py -q`
  - `frontend npm run lint && npm run build`
- 完成标准：
  - 总览页面可稳定展示核心摘要；
  - 空数据/异常分支有可读提示，不泄露敏感信息。

当前状态（2026-05-27）：

- 已落地后端只读聚合接口：`GET /operations/summary`
- 已落地前端只读入口：`/operations`
- 汇总字段覆盖：health/version、deployment check 摘要、runtime metrics、tasks/approvals 计数、audit 最近事件、pilot reports/demo evidence 摘要
- 空目录与空数据返回可读空状态，不触发写操作，不触发真实 LLM

### Phase 11.3：真实 LLM opt-in 实测执行与报告归档（P1）

- 目标：
  - 在用户显式提供环境变量时执行受控实测并归档证据。
- 修改范围：
  - `docs/real_llm_pilot_execution_log_v30.md` 与 `docs/reports/real_llm_pilot/` 归档流程。
- 不做什么：
  - 环境缺失时不伪造成功报告；
  - 不把 API key/token 写入仓库。
- 验证命令：
  - opt-in 条件满足时执行 `scripts/real_llm_smoke.ps1`
  - 条件不满足时记录 skipped（不失败）
- 完成标准：
  - executed 或 skipped 结果可追踪；
  - 报告字段完整且脱敏边界有效。

当前状态（2026-05-27）：

- 已新增 v3.1 执行记录：`docs/real_llm_pilot_execution_log_v31.md`
- 本轮因 opt-in 环境变量缺失，记录 `status=skipped`
- 未执行真实外网 LLM，未伪造成功报告，等待用户手动注入环境后重试

### Phase 11.4：OIDC/SSO 最小真实 IdP 配置演练文档（P1）

- 目标：
  - 完善真实 IdP 接入演练文档与最小配置排障路径。
- 修改范围：
  - OIDC 配置 runbook、排障 checklist、示例配置说明（不含密钥）。
- 不做什么：
  - 不宣称生产级 SSO 已完成；
  - 不引入复杂统一身份平台改造。
- 验证命令：
  - `python -m pytest tests/test_oidc_config_v75.py -q`
  - `/auth/oidc/status` 配置状态检查（仅返回存在性状态）
- 完成标准：
  - OIDC 最小接入与失败场景有清晰文档；
  - 不泄露 `client_secret` 原文。

### Phase 11.5：运维 polish（P2）

- 目标：
  - 增强备份恢复检查清单、日志排障索引、常见故障 runbook 的可执行性。
- 修改范围：
  - `docs/operations_monitoring_backup_drill_v30.md`、`docs/deployment_runbook.md`、相关故障索引文档。
- 不做什么：
  - 不引入 Prometheus/Grafana/ELK 等复杂平台依赖。
- 验证命令：
  - `python -m pytest tests/test_runtime_hardening_v055.py -q`
  - `docker compose config`
- 完成标准：
  - 运维常见问题有标准处理路径；
  - 备份恢复演练步骤可复用。

### Phase 11.6：v3.1 release prep（P2）

- 目标：
  - 完成版本同步、发布文档、验证矩阵与 tag 决策前复核。
- 修改范围：
  - release notes / release review / readiness checklist。
- 不做什么：
  - 不提前打 tag；
  - 不提前创建 GitHub Release。
- 验证命令：
  - 以 release prep 当轮全量回归为准（含 pytest / compose / frontend）。
- 完成标准：
  - 发布材料完整、口径一致、边界声明准确。

## 4. 推荐优先级

- P0：Phase 11.1 + 11.2（优先提升产品演示与验收效率）
- P1：Phase 11.3 + 11.4
- P2：Phase 11.5 + 11.6

## 5. 边界声明

- 默认 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- 真实 LLM 仅 opt-in。
- 不提交任何密钥与凭据（API key/token/client_secret/JWT_SECRET/DATABASE_URL/REDIS_URL）。
- 不默认接入真实外部 MCP。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
