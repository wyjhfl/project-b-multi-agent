# v3.1.0 发布交接检查（手动 GitHub Release 前）

## 1) Tag 信息

- tag name: `v3.1.0`
- tag message: `Project B v3.1.0 - Productization Enhancement`
- tag object: `f32a589e4e0fa7ae10280bf7dd1f428355b85199`
- dereferenced commit: `4ffb8044ccc0f1fb62c570308c8c9c4c8c46a99a`

校验命令：

```bash
git rev-parse HEAD
git rev-parse "v3.1.0^{}"
git rev-parse "v3.0.0^{}"
git ls-remote --tags origin v3.1.0
```

## 2) GitHub Release 状态

- 当前状态：**尚未创建 v3.1.0 GitHub Release**（需手动创建）。

## 3) 手动创建 Release 信息

- Tag: `v3.1.0`
- Title: `Project B v3.1.0 - Productization Enhancement`
- Description: 使用 `RELEASE_NOTES_v3.1.0.md`

## 4) 验证摘要（release prep 基线）

- `python -m pytest -q`：`754 passed, 4 skipped`
- `docker compose config`：通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败
- 注入临时 `JWT_SECRET/DATABASE_URL/REDIS_URL` 后 prod compose config：通过
- `frontend npm run lint`：通过
- `frontend npm run build`：通过

## 5) 边界声明

- 本轮未执行真实外网 LLM。
- 默认 `fake/offline`。
- 默认 `pytest/CI` 不调用真实 LLM。
- Phase 11.3 本轮为 `skipped`（opt-in 环境变量缺失）。
- v3.1.0 不等于公网生产直接上线。
- v3.1.0 不等于真实 LLM 生产验收完成。
- v3.1.0 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## 6) 下一步

1. 手动创建 `v3.1.0` GitHub Release。
2. Release 创建后补一条 `release-created` 文档提交（仅收口记录，不改 tag）。
3. 之后 `main` 超前 `v3.1.0` tag 属于发布后文档收口与后续规划演进。
