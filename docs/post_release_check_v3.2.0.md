# v3.2.0 发布交接检查（Post Release Handoff）

## 1) Tag 信息记录

- tag name: `v3.2.0`
- tag message: `Project B v3.2.0 - Acceptance & Observability Enhancement`
- tag object: `14fc3c6f34defb878f6c3f59d8b7e6128ed6c00e`
- dereferenced commit: `3c12985d15062328efe5711ee939ca28ba4dbacf`

## 2) GitHub Release 状态

- 当前状态：**已由用户手动创建 GitHub Release**。
- Release title: `Project B v3.2.0 - Acceptance & Observability Enhancement`
- Release notes 来源：`RELEASE_NOTES_v3.2.0.md`

## 3) 手动创建 GitHub Release 信息

- Tag: `v3.2.0`
- Title: `Project B v3.2.0 - Acceptance & Observability Enhancement`
- Description: 使用 `RELEASE_NOTES_v3.2.0.md`

## 4) 验证摘要（release prep 基线）

- `python -m pytest -q`: `768 passed, 4 skipped`
- `docker compose config`: 通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败
- 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后 prod compose config：通过
- `frontend npm run lint` / `frontend npm run build`：通过

## 5) 边界声明

- 未执行真实外网 LLM
- 默认 fake/offline
- 默认 pytest/CI 不调用真实 LLM
- Phase 12.5 本轮为 skipped（opt-in 环境变量不完整）
- 不等于公网生产直接上线
- 不等于真实 LLM 生产验收完成
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成

## 6) 发布后状态与下一步

- `v3.2.0` tag 未移动，仍指向 `3c12985d15062328efe5711ee939ca28ba4dbacf`。
- 本轮及本阶段未执行真实外网 LLM。
- 当前 main 超前 `v3.2.0` tag 属于发布后文档收口。

下一步建议：

1. 进入 v3.3 或下一阶段路线规划文档。
2. 继续保持默认 fake/offline 与默认 pytest/CI 不调用真实 LLM 的基线。
