# v2.8.0 发布交接检查

## 1. v2.8.0 tag 信息

- tag：`v2.8.0`（annotated tag）
- tag message：`Project B v2.8.0 - Controlled Real LLM Pilot`
- tag object：`13992df663b29fdc02eaa8f1a8b36d57b584b10a`
- tag 解引用 commit：`7ef45bf9af9bec9e3c48b65f88671625b5ab23b0`

## 2. HEAD 与 tag 解引用一致性校验

执行：

```bash
git rev-parse HEAD
git rev-parse "v2.8.0^{}"
```

预期：两者均为 `7ef45bf9af9bec9e3c48b65f88671625b5ab23b0`。

## 3. 远端 tag 校验命令

执行：

```bash
git ls-remote --tags origin v2.8.0
```

预期：返回 `refs/tags/v2.8.0`。

## 4. GitHub Release 手动创建与结果记录

### 4.1 手动创建步骤（留档）

1. 打开仓库 Releases 页面。
2. 点击 “Draft a new release”。
3. 选择 tag：`v2.8.0`。
4. 填写标题：`Project B v2.8.0 - Controlled Real LLM Pilot`。
5. 将 `RELEASE_NOTES_v2.8.0.md` 内容复制为 Release 描述。
6. 核对边界声明后手动发布。

### 4.2 本次发布结果

- GitHub Release：**已由用户手动创建**。
- Release title：`Project B v2.8.0 - Controlled Real LLM Pilot`
- Release notes 来源：`RELEASE_NOTES_v2.8.0.md`
- `v2.8.0` tag 仍指向：`7ef45bf9af9bec9e3c48b65f88671625b5ab23b0`
- 当前 main 已超前 tag（发布后文档收口提交），但 tag 未移动、未删除、未重建。

## 5. 验证摘要

- `pytest llm/preflight+acceptance+smoke+judge`：`21 passed, 4 skipped`
- `pytest runtime_hardening+mcp_stdio`：`34 passed`
- `pytest -q`：`730 passed, 4 skipped`
- `docker compose config`：通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败
- 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后 prod compose config：通过
- `frontend npm run lint`：通过
- `frontend npm run build`：通过

## 6. 当前边界声明

- 本轮**未执行真实外网 LLM**。
- 默认路径保持 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- v2.8.0 定位为 Controlled Real LLM Pilot，不等于真实 LLM 生产验收完成。
- 不等于公网生产可直接上线。
- 不宣称真实外部 MCP 生产验收完成。
- 生产级 SSO/OIDC、多租户、复杂 BI 仍未完成。
- `v2.8.0` tag 未移动、未删除、未重建。

## 7. 下一阶段建议

推荐优先进入：**v2.9 Real LLM Controlled Pilot Evidence**，先完成真实 LLM 受控试点证据归档（场景、预算、回退、审计、风险与报告模板闭环）。

备选方向：v3.0 production hardening continuation。
