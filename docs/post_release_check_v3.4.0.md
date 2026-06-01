# v3.4.0 发布后检查（Release 已创建）

## 1. Tag 快照

- tag name: `v3.4.0`
- tag message: `Project B v3.4.0 - Pilot Hardening & Operator Experience`
- tag object: `99ee3d5f3a0328b5d787f9ada34592383d29bef3`
- dereferenced commit: `868dd76496a08821dbb0a133cb28d0a62a51a5d7`

## 2. 历史 tag 保持不变

- `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`
- `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
- `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
- `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`

## 3. GitHub Release 状态

- Status: **已由用户手动创建**。
- Release 标题：`Project B v3.4.0 - Pilot Hardening & Operator Experience`
- Release notes 来源：`RELEASE_NOTES_v3.4.0.md`
- `v3.4.0` tag 保持不变，未移动、未删除、未重建。

## 4. 验证摘要

- `git status -sb`: clean, `main...origin/main`
- `HEAD` = `origin/main` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`
- `git rev-parse "v3.4.0^{}"` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`
- `git ls-remote --tags origin "v3.4.0*"`:
  - `refs/tags/v3.4.0` = `99ee3d5f3a0328b5d787f9ada34592383d29bef3`
  - `refs/tags/v3.4.0^{}` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`
- v3.4 相关测试：`19 passed`
- v3.4.0 release prep 全量回归记录：`807 passed, 4 skipped, 1 warning`
- `docker compose config`: passed
- prod compose 缺少 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 时按预期失败，注入临时变量后通过，临时变量已清理
- frontend `npm run lint` / `npm run build`: passed
- release-created 文档收口验证：
  - `tests/test_runtime_hardening_v055.py`: `11 passed`
  - `docker compose config`: passed

## 5. 边界声明

- 本轮 release-created 文档收口未执行真实外网 LLM。
- 默认路径仍为 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- v3.4.0 是企业内网试点硬化与操作员体验增强交付，不等于公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 真实外部 MCP Server、生产级 SSO/OIDC、多租户、复杂 BI 仍需后续专项验收。
- main 超前 `v3.4.0` tag 属于发布后文档收口。

## 6. 下一步

1. v3.4.0 release-created 文档收口完成。
2. 后续可进入 v3.5 或下一阶段路线规划。
