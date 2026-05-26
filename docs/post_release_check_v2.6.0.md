# v2.6.0 发布交接检查记录

## 1. 版本与标签信息

- 当前发布版本：`v2.6.0`
- 远端标签：`refs/tags/v2.6.0`
- 当前主分支发布提交：`f32bd9d898fa130b86830a81aa1d7932cf930d5e`

## 2. HEAD 与 tag 解引用校验

在仓库根目录执行：

```bash
git rev-parse HEAD
git rev-parse "v2.6.0^{}"
```

期望：两条命令输出相同提交哈希，表示 `v2.6.0` 解引用后指向当前发布提交。

## 3. 远端 tag 校验命令

```bash
git ls-remote --tags origin v2.6.0 refs/tags/v2.6.0^{}
```

说明：

- `refs/tags/v2.6.0` 为 annotated tag 对象；
- `refs/tags/v2.6.0^{}` 为解引用后的实际提交对象。

## 4. GitHub Release 手动创建说明

本轮不自动创建 GitHub Release。如需手动创建：

1. 打开发布页面：`https://github.com/wyjhfl/project-b-multi-agent/releases/new`
2. 选择 tag：`v2.6.0`
3. 标题建议：`Project B v2.6.0 - Engineering Readiness`
4. 描述内容来源：`RELEASE_NOTES_v2.6.0.md`

## 5. 验证摘要

- 全量回归：`671 passed, 4 skipped`
- 前端验证：`npm run lint`、`npm run build` 通过
- 容器配置：`docker compose config` 通过
- 生产 override 校验：
  - 缺少必填敏感变量时，`docker compose -f docker-compose.yml -f docker-compose.prod.yml config` 按预期失败
  - 注入临时安全变量后，同命令通过
- 脚本验证：`scripts/prod_config_check.ps1` 在 development 环境输出 warning 且通过

## 6. 当前边界声明

- 当前定位：企业内网试点准生产可投入使用
- 不等于公网生产可直接上线
- 不含生产级 SSO/OIDC
- 不含多租户
- 不含复杂 BI
- 不含真实外部 MCP Server 生产验收
- 真实 LLM 仍为 opt-in 验收路径，不进入默认测试与默认运行路径
