# Real LLM Pilot Runbook（真实模型试点：只差一个 key）

一页说明：拿到 API Key 后如何用 `scripts/run_llm_pilot.py` 跑通"preflight -> NL2SQL eval 抽样 -> 脱敏报告"的受控试点，以及没有 key 时如何诚实演示。

## 1. 三条命令跑通试点（PowerShell）

```powershell
# 1) 显式开启真实试点开关 + 声明 provider（openai_compatible 纯 httpx，无需安装 litellm）
$env:REAL_LLM_ACCEPTANCE_ENABLED = "true"; $env:REAL_LLM_PROVIDER = "openai_compatible"

# 2) 配置模型 / 网关地址 / API Key（key 只放环境变量，永不落盘）
$env:REAL_LLM_MODEL = "gpt-4o-mini"; $env:REAL_LLM_BASE_URL = "https://api.openai.com/v1"; $env:OPENAI_API_KEY = "<your-key>"

# 3) 运行试点（preflight 网络探测 + 约 15-20 条 NL2SQL eval 用例 + 报告落盘）
python scripts/run_llm_pilot.py
```

bash 等价写法：`export REAL_LLM_ACCEPTANCE_ENABLED=true REAL_LLM_PROVIDER=openai_compatible REAL_LLM_MODEL=gpt-4o-mini REAL_LLM_BASE_URL=https://api.openai.com/v1 OPENAI_API_KEY=<your-key> && python scripts/run_llm_pilot.py`

环境变量说明（对齐项目 `REAL_LLM_*` 命名；`PILOT_*` 为单次运行的便捷覆盖，优先级更高）：

| 变量 | 说明 |
| --- | --- |
| `REAL_LLM_ACCEPTANCE_ENABLED` | 真实试点总开关，必须显式 `true`，否则脚本拒绝生成报告 |
| `REAL_LLM_PROVIDER` / `PILOT_PROVIDER` | `openai_compatible`（推荐，纯 httpx）或 `litellm`（需 `pip install .[litellm]`） |
| `REAL_LLM_MODEL` / `PILOT_MODEL` | 模型名，如 `gpt-4o-mini`、`deepseek-chat`、`qwen-plus` |
| `REAL_LLM_BASE_URL` / `PILOT_BASE_URL` | OpenAI-compatible 网关地址（`openai_compatible` 必填） |
| `REAL_LLM_API_KEY_ENV` | 存放 key 的环境变量名，默认 `OPENAI_API_KEY`；也可直接设 `PILOT_API_KEY` |
| `REAL_LLM_PILOT_REPORT_DIR` | 报告输出目录，默认 `docs/reports/real_llm_pilot/` |

常用参数：`--limit 15`（抽样条数，默认 20）、`--output-dir <dir>`、`--skip-network-probe`（仅排查用）。

## 2. 预期产物

- 终端：preflight 检查逐项结果、逐条用例 pass/FAIL、`[summary]` 一行汇总（成功率/降级率/延迟 p50 p95/token/成本/bad case 数）。
- `docs/reports/real_llm_pilot/<时间戳>_llm-pilot-real.json`：结构化报告，含 `provider` / `model` / `base_url_summary`（脱敏，仅保留 host）、`run_mode`、`eval_summary`（成功率、降级率、latency_p50_ms/latency_p95_ms、token 与成本、逐条 bad case）与逐条案例明细。
- 同名 `.md`：markdown 摘要，可直接贴进面试材料或复盘文档。
- 报告统一经 `app/harness/llm/pilot_report.py` 脱敏：不含 prompt 原文、不含密钥原文、不含数据库密码。

退出码：`0` 报告已生成；`2` 诚实拒绝（配置不完整，不产出任何报告文件）；`1` preflight/运行失败。

## 3. 没有 key 时的诚实演示（dry-run）

```powershell
python scripts/run_llm_pilot.py --dry-run
```

- 用 fake provider 走完全流程（preflight、eval、报告落盘），全程离线零成本。
- 终端与报告均显著标注 **DRY RUN / provider=fake**，`run_mode=dry_run`，防止被误当真实模型证据。
- 未配置真实 provider 时直接运行（不带 `--dry-run`）会被拒绝并打印上面第 1 节的配置指引——这是刻意设计的护栏。

## 4. 预期成本量级（粗估，按 2025-2026 典型价格）

单次试点约 17 条用例，每条 prompt 约 600-900 tokens（含 schema）、completion 约 100-200 tokens，合计约 1.5 万-2 万 tokens：

| 模型档位（示例） | 参考单价（USD / 1M tokens, in/out） | 单次试点估算 |
| --- | --- | --- |
| 轻量档（gpt-4o-mini / deepseek-chat 级） | ~0.15 / 0.60 | < $0.01 |
| 中档（gpt-4o / qwen-max 级） | ~2.5 / 10 | ~$0.05-0.08 |
| 旗舰档（claude-sonnet / o 系列级） | ~3 / 15 | ~$0.06-0.10 |

即使反复跑几十次也在 $1-3 量级。若要在报告中输出非零 `cost`，配置 `LLM_COST_PER_1K_PROMPT_TOKENS_USD` / `LLM_COST_PER_1K_COMPLETION_TOKENS_USD`（否则 token 数照常统计，cost 记 0）。

## 5. 边界声明

- 本试点是受控证据收集（controlled pilot），不等于生产验收；生产验收另见 `docs/deployment_runbook.md` 与 `/llm/preflight` 两阶段流程。
- 默认配置（fake provider / mock generator）行为不变：不设置任何 `REAL_LLM_*` 变量时，`pytest` 与 CI 完全离线可跑。
