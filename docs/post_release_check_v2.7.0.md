# v2.7.0 发布交接检查

## 1. v2.7.0 tag 信息

- tag：`v2.7.0`（annotated tag）
- tag message：`Project B v2.7.0 - Production Security Baseline`
- tag 解引用 commit：`2076111cb786df76a941ebf28f550f68f4131147`

校验命令：

```bash
git rev-parse "v2.7.0^{}"
```

## 2. GitHub Release 状态

- GitHub Release 已手动创建。
- Release title：`Project B v2.7.0 - Production Security Baseline`
- Release description 来源：`RELEASE_NOTES_v2.7.0.md`

## 3. 关键提交轨迹

- v2.7.0 tag commit：`2076111cb786df76a941ebf28f550f68f4131147`
- tag 后 CI 修复 commit：`21ab5f75053427d277c27f7155fbd7f457237fa2`（`ci: validate production compose required envs`）
- release handoff commit：`47c4ce0`
- 当前 main 已超前 tag，但 `v2.7.0` tag 不移动。

## 4. 验证摘要

- 后端测试基线：`727 passed, 4 skipped`
- 前端验证：`npm run lint`、`npm run build` 均通过
- `docker compose config` 通过
- prod override 验证：
  - 缺变量（`JWT_SECRET` / `DATABASE_URL` / `REDIS_URL`）时预期失败
  - 注入临时安全变量后通过

## 5. CI 说明（tag 后补丁）

- `v2.7.0` tag 仍指向 `2076111cb786df76a941ebf28f550f68f4131147`
- tag 后 main 新增 CI workflow 修复 commit：`21ab5f75053427d277c27f7155fbd7f457237fa2`
- 修复内容仅限 GitHub Actions 的 prod compose config 验证方式：
  1. 缺变量时必须失败（安全语义校验）
  2. 注入 CI 临时变量后必须成功
- `v2.7.0` tag 未移动、未删除、未重建

参考 run（main 最新 CI）：
- workflow：CI
- commit：`21ab5f7`
- run：`26488870021`
- 状态：completed successfully

## 6. 边界声明

- 当前定位：企业内网试点准生产安全基线能力增强
- 不等于公网生产可直接上线
- OIDC/SSO 当前仅为最小接入骨架与配置预检
- 真实 LLM 仍为 opt-in，不进入默认 CI
- 不宣称真实外部 MCP 生产验收完成
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 已完成
