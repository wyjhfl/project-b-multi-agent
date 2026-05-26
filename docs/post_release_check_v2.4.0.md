# v2.4.0 发布交接记录

## 1. Tag 信息

- Tag 名称：`v2.4.0`
- Tag 类型：annotated tag
- Tag 说明：`Project B v2.4.0 - Operator Console Pilot`
- 当前主分支提交：`e3c7489dcad3445d351c60a1b00d5871b86609fb`

## 2. Tag 指向 HEAD 的确认方式

在仓库根目录执行：

```bash
git rev-parse HEAD
git rev-parse "v2.4.0^{}"
git ls-remote --tags origin v2.4.0
```

判定标准：

- `git rev-parse HEAD` 与 `git rev-parse "v2.4.0^{}"` 输出一致；
- 远端存在 `refs/tags/v2.4.0`。

## 3. GitHub Release 手动创建说明

本仓库当前未自动创建 GitHub Release，需手动创建：

1. 打开 GitHub Releases 新建页面。
2. 选择 tag：`v2.4.0`。
3. 标题建议：`Project B v2.4.0 - Operator Console Pilot`。
4. 描述内容来源：`RELEASE_NOTES_v2.4.0.md`（建议完整复制）。

## 4. Release 描述来源

- 发布说明统一以仓库文件 `RELEASE_NOTES_v2.4.0.md` 为准。
- 若网页发布内容与该文件冲突，以仓库文件口径优先，并在后续补充说明中修正。

## 5. 默认离线演示命令

默认离线路径保持不变，不依赖真实 LLM、真实外部 MCP：

```bash
python -m pytest tests/test_runtime_hardening_v055.py -q
python -m pytest -q
```

## 6. Docker demo scripts 使用方式

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_up.ps1
powershell -ExecutionPolicy Bypass -File scripts/demo_smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/demo_down.ps1
```

说明：

- `demo_up`：构建并启动 `app + frontend`；
- `demo_smoke`：检查 `/api/health`、`/`、`/tasks`、`/approvals`、`/rbac`、`/tools`、`/nl2sql`、`/audit`、`/metrics`、`/observability`；
- `demo_down`：停止并清理容器与网络。

## 7. 当前已知边界

- 默认仍为离线可跑演示路径，不默认调用真实 LLM。
- 不接真实外部 MCP Server 作为默认验收依赖。
- 不宣称真实 LLM 生产验收完成。
- 不宣称真实外部 MCP Server 生产验收完成。
- 不宣称生产级 SSO、多租户、复杂 BI 已完成。
- 不宣称完整 LangGraph native Command resume 已完成。

## 8. 下一阶段建议

建议进入 v2.5 的“真实 LLM 可选验收包”规划与分阶段实施：

1. 先做 provider preflight 与配置验证；
2. 再做 opt-in 的真实 LLM smoke，且不进入默认 CI；
3. 最后补齐 token/cost/budget/cache/fallback 与 LLMJudge 的可选验收闭环。
