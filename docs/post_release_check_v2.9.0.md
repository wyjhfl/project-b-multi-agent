# v2.9.0 发布交接检查

## 1. v2.9.0 tag 信息

- tag：`v2.9.0`（annotated tag）
- tag message：`Project B v2.9.0 - Real LLM Controlled Pilot Evidence`
- tag object（`git rev-parse v2.9.0`）：`33ab858c95a653e00fcea92ddde4f13c9bd6edca`
- tag 解引用 commit（`git rev-parse "v2.9.0^{}"`）：`eccc9708b493af25d30ac6e5da08cdd92f461d48`
- HEAD commit：`eccc9708b493af25d30ac6e5da08cdd92f461d48`

## 2. HEAD 与 tag 一致性校验命令

```bash
git rev-parse HEAD
git rev-parse "v2.9.0^{}"
```

预期：两条命令输出一致。

## 3. 远端 tag 校验命令

```bash
git ls-remote --tags origin v2.9.0
```

预期：返回 `refs/tags/v2.9.0`。

## 4. GitHub Release 手动创建步骤

1. 打开仓库 Releases 页面。  
2. 选择 **Draft a new release**。  
3. Tag 选择：`v2.9.0`。  
4. 标题填写：`Project B v2.9.0 - Real LLM Controlled Pilot Evidence`。  
5. 描述内容复制自：`RELEASE_NOTES_v2.9.0.md`。  
6. 检查无密钥/凭据后发布。

## 5. 验证摘要

- `python -m pytest tests/test_llm_pilot_reports_v94.py -q`：`6 passed`
- `python -m pytest tests/test_real_llm_judge_smoke_v54.py tests/test_real_llm_smoke_v52.py -q`：`5 passed, 4 skipped`
- `python -m pytest tests/test_real_llm_pilot_report_v91.py tests/test_llm_acceptance_v53.py -q`：`19 passed`
- `python -m pytest tests/test_runtime_hardening_v055.py tests/test_mcp_stdio_client_v31.py -q`：`34 passed`
- `python -m pytest -q`：`750 passed, 4 skipped`
- `docker compose config`：通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败
- 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后 prod compose config：通过
- `frontend npm run lint`：通过
- `frontend npm run build`：通过

## 6. 边界声明

- 本轮未执行真实外网 LLM。
- 默认路径保持 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- v2.9.0 是 Real LLM Controlled Pilot Evidence，不等于真实 LLM 生产验收完成。
- 不等于公网生产可直接上线。
- 不宣称真实外部 MCP 生产验收完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成。
- v2.8.0 tag 与 GitHub Release 已发布且未移动（`v2.8.0^{} = 7ef45bf9af9bec9e3c48b65f88671625b5ab23b0`）。

## 7. 下一阶段建议

- 推荐先手动创建 v2.9.0 GitHub Release。
- Release 后补一条文档提交记录“GitHub Release 已创建”。
- 后续路线建议进入 v3.0 生产落地最终阶段规划：
  - 真实 LLM 受控试点实测报告归档
  - 生产部署演练
  - 运维监控与备份恢复
  - 安全复核
  - 最终 Go/No-Go
