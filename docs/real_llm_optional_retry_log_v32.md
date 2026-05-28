# v3.2 Phase 12.5：Optional Real LLM Evidence Retry 执行记录

## 1. 执行目标

- 仅在用户显式提供完整 opt-in 环境变量时执行真实外网 LLM retry。
- 若环境变量不完整，必须 `status=skipped`，不得伪造成功报告。
- 全程保持脱敏边界：不记录 prompt 原文、不记录密钥原文。

## 2. 必需环境变量检查（2026-05-28）

必需变量：

- `REAL_LLM_SMOKE_ENABLED`
- `REAL_LLM_ACCEPTANCE_ENABLED`
- `REAL_LLM_PREFLIGHT_ENABLED`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`
- `REAL_LLM_API_KEY_ENV` 指向的真实 key 环境变量

检查结果：

- `status=skipped`
- 缺失变量：
  - `REAL_LLM_SMOKE_ENABLED`
  - `REAL_LLM_ACCEPTANCE_ENABLED`
  - `REAL_LLM_PREFLIGHT_ENABLED`
  - `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
  - `REAL_LLM_MODEL`
  - `REAL_LLM_API_KEY_ENV`
  - `REAL_LLM_API_KEY_ENV` target key env（未检测，因 env 名缺失）

## 3. 执行与归档结果

- 是否执行真实外网 LLM：**否**
- 是否执行 `scripts/real_llm_smoke.ps1`：**否（按规则 skipped）**
- 是否生成真实外网 pilot report：**否**
- 是否生成 acceptance snapshot：**否（本轮仅做 skipped 归档）**
- 是否生成 demo artifact bundle：**否（本轮仅做 skipped 归档）**

## 4. 结论与下一步

- 本轮结论：`skipped`（环境变量不完整，符合边界约束）。
- 未将失败/缺失包装为成功。
- 等待用户在安全环境手动注入完整 opt-in 变量后重试。

## 5. 脱敏与边界声明

- 未执行真实外网 LLM。
- 默认 fake/offline 仍保持。
- 默认 pytest/CI 不调用真实 LLM 仍保持。
- 不提交 API key/token/client_secret/password/JWT_SECRET/DATABASE_URL/REDIS_URL 明文。
- 不宣称公网生产可直接上线。
- 不宣称真实 LLM 生产验收已完成。
- 不宣称生产级 SSO/OIDC、多租户、复杂 BI 全量完成。
