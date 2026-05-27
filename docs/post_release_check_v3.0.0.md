# v3.0.0 发布交接检查

## 1. v3.0.0 tag 信息

- tag name：`v3.0.0`
- tag message：`Project B v3.0.0 - Final Production Landing`
- tag object（`git rev-parse v3.0.0`）：`daaa65fa36a37067165c326c6dc071c5160acf54`
- dereferenced commit（`git rev-parse "v3.0.0^{}"`）：`fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- HEAD（`git rev-parse HEAD`）：`fa5b07b3ffb373d2f1060f38b6ef0a4d31b5194d`
- v2.9.0 dereferenced commit（`git rev-parse "v2.9.0^{}"`）：`eccc9708b493af25d30ac6e5da08cdd92f461d48`

一致性结论：

- `HEAD == v3.0.0^{}`（一致）
- v2.9.0 tag 保持不变（未移动）

## 2. 远端 tag 校验

命令：

```bash
git ls-remote --tags origin v3.0.0
```

结果：

- 远端存在 `refs/tags/v3.0.0`。

## 3. GitHub Release 状态

- 当前状态：**尚未创建 GitHub Release**（本交接文档仅准备手动发布信息）。

## 4. 手动创建 GitHub Release 信息

- Tag：`v3.0.0`
- Title：`Project B v3.0.0 - Final Production Landing`
- Description 来源：`RELEASE_NOTES_v3.0.0.md`

## 5. 验证摘要

- `python -m pytest -q`：`750 passed, 4 skipped`
- `docker compose config`：通过
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml config`（缺变量）：按预期失败
- 注入临时 `JWT_SECRET` / `DATABASE_URL` / `REDIS_URL` 后 prod compose config：通过
- `frontend npm run lint`：通过
- `frontend npm run build`：通过

## 6. 边界声明

- 本轮未执行真实外网 LLM。
- 默认 fake/offline 路径保持不变。
- 默认 pytest/CI 不调用真实 LLM。
- v3.0.0 定位为企业内网试点/准生产演示落地。
- 不等于公网生产直接上线。
- 不等于真实 LLM 生产验收完成。
- 不等于生产级 SSO/OIDC、多租户、复杂 BI 全量完成。

## 7. 下一步建议

1. 手动创建 v3.0.0 GitHub Release（按本文件第 4 节信息）。
2. Release 创建后补一条文档提交，记录“GitHub Release 已创建”。
