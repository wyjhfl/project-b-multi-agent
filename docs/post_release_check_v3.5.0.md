# v3.5.0 发布后检查（Release 已创建）

## 1. Tag 快照

- tag name: `v3.5.0`
- tag message: `Project B v3.5.0 - Controlled Pilot Expansion & Evidence Operations`
- remote tag object: `1bae4345334608e1ee54e3f77626f5cde6f28025`
- local pre-created tag object: `93abc4b56756ab705cbb92894682291ac5e54d14`
- dereferenced commit: `90cf1b3a325032b6d865c82d11035c27cfee3017`
- 说明：由于 `github.com:443` Git HTTPS 在本机不可达，本轮通过 GitHub API 创建远端 annotated tag/ref；远端 tag 与本地预创建 tag 的 object SHA 不同，但均指向同一 release commit。未移动、删除或重建远端 tag。

## 2. 历史 tag 保持不变

- `v3.4.0^{}` = `868dd76496a08821dbb0a133cb28d0a62a51a5d7`
- `v3.3.0^{}` = `0399b84de5c2232a451d02ef37a8b181d0b01ebe`
- `v3.2.0^{}` = `3c12985d15062328efe5711ee939ca28ba4dbacf`
- `v3.1.0^{}` = `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`
- `v3.0.0^{}` = `fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`

## 3. GitHub Release 状态

- Status: **已创建**。
- Release 标题：`Project B v3.5.0 - Controlled Pilot Expansion & Evidence Operations`
- Release notes 来源：`RELEASE_NOTES_v3.5.0.md`
- Release URL：https://github.com/wyjhfl/project-b-multi-agent/releases/tag/v3.5.0
- Release 属性：`draft=false`，`prerelease=false`
- `v3.5.0` 远端 tag 保持不变，未移动、未删除、未重建。

## 4. 验证摘要

- `git status -sb`: clean, `main...origin/main`
- `HEAD` = `origin/main` = `90cf1b3a325032b6d865c82d11035c27cfee3017`
- GitHub API `refs/tags/v3.5.0`:
  - `ref_type` = `tag`
  - `tag_sha` = `1bae4345334608e1ee54e3f77626f5cde6f28025`
  - `target_type` = `commit`
  - `target_sha` = `90cf1b3a325032b6d865c82d11035c27cfee3017`
- GitHub API Release:
  - `tag_name` = `v3.5.0`
  - `target_commitish` = `main`
  - `draft` = `false`
  - `prerelease` = `false`
- v3.5 release prep 全量回归记录：`831 passed, 4 skipped, 1 warning`
- Phase 15.1~15.5 目标测试：`24 passed`
- runtime/health/MCP stdio version 回归：`36 passed, 1 warning`
- final light regression：`41 passed, 1 warning`
- `docker compose config`: passed
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`: passed（仅使用占位环境变量做配置解析）
- frontend `npm run lint` / `npm run build`: passed

## 5. 边界声明

- 本轮 release-created 收口未执行真实外网 LLM。
- 默认路径仍为 fake/offline。
- 默认 pytest/CI 不调用真实 LLM。
- v3.5.0 是受控试点扩展与证据运营交付，不等于公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
- 真实外部 MCP Server、生产级 SSO/OIDC、多租户、复杂 BI 仍需后续专项验收。
- main 超前 `v3.5.0` tag 属于发布后文档收口。

## 6. 下一步

1. v3.5.0 release-created 文档收口完成。
2. 后续可进入 v3.6 Enterprise Identity & Tenant Boundary 或下一阶段路线规划。
