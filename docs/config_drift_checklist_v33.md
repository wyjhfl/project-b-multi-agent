# v3.3 Phase 13.2：Config Drift Checklist（只读）

## 1. 目标与边界

- 目标：建立 `.env.example`、`.env.production.example`、deployment guard、runtime settings 的配置漂移检查清单。
- 本阶段仅做**只读检查**与结果归档，不自动改配置。
- 不删除用户数据、不自动清理报告、不写入真实密钥值。
- 不执行真实外网 LLM。

## 2. 关键检查范围

### 2.1 `.env.example` 与 `.env.production.example` 对齐

- 检查两份模板中的键集合差异：
  - `missing_in_example`
  - `missing_in_production_example`
- 重点关注生产必需变量：
  - `JWT_SECRET`
  - `DATABASE_URL`
  - `REDIS_URL`

### 2.2 deployment guard 关键项

对齐并复核以下类别（示例）：

- 应用与鉴权：`APP_ENV`、`AUTH_ENABLED`、`RBAC_ENABLED`、`JWT_SECRET`
- 安全与防护：`CORS_ALLOW_ORIGINS`、`SECURITY_HEADERS_ENABLED`、`REQUEST_SIZE_LIMIT_*`、`RATE_LIMIT_*`
- 日志与审计：`STRUCTURED_LOGGING_ENABLED`、`LOG_REDACTION_ENABLED`、`LOG_LEVEL`、`AUDIT_*`
- 存储与连接：`STORAGE_BACKEND`、`DATABASE_URL`、`REDIS_ENABLED`、`REDIS_URL`
- OIDC：`OIDC_*`
- real LLM opt-in：`REAL_LLM_*`

### 2.3 runtime settings 关键项

- 检查 `app/core/config.py` 中 Settings 映射的环境变量键是否在模板中有对应项。
- 检查不读取真实值，仅检查“键是否存在于模板”。

### 2.4 OIDC 配置项

- `OIDC_ENABLED`
- `OIDC_ISSUER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET_ENV`
- `OIDC_REDIRECT_URI`
- `OIDC_SCOPES`
- `OIDC_ROLE_CLAIM`
- `OIDC_DEFAULT_ROLE`
- `OIDC_ALLOWED_ROLES`
- `OIDC_REQUIRE_HTTPS`

### 2.5 audit export / redaction 配置项

- `AUDIT_RETENTION_ENABLED`
- `AUDIT_RETENTION_DAYS`
- `AUDIT_EXPORT_ENABLED`
- `AUDIT_EXPORT_MAX_ROWS`
- `AUDIT_EXPORT_FORMAT`
- `AUDIT_EXPORT_REDACTION_ENABLED`

### 2.6 real LLM opt-in 配置项

- `REAL_LLM_SMOKE_ENABLED`
- `REAL_LLM_ACCEPTANCE_ENABLED`
- `REAL_LLM_PREFLIGHT_ENABLED`
- `REAL_LLM_PREFLIGHT_NETWORK_CHECK`
- `REAL_LLM_MODEL`
- `REAL_LLM_API_KEY_ENV`
- `REAL_LLM_BASE_URL`

## 3. 只读脚本（可选）

- 脚本：`scripts/config_drift_check.py`
- 默认输出目录：`docs/reports/config_drift/`
- 支持覆盖：`--output-dir`
- 输出格式：JSON + Markdown

示例：

```bash
python scripts/config_drift_check.py
python scripts/config_drift_check.py --output-dir .tmp_config_drift_check
```

## 4. 输出字段说明

至少包含：

- `generated_at`
- `commit`
- `checked_files`
- `missing_in_example`
- `missing_in_production_example`
- `deployment_guard_related`
- `oidc_related`
- `audit_related`
- `real_llm_related`
- `compose_required_env`
- `warnings`
- `boundary_declarations`

## 5. 恢复与风险原则

- 发现 drift 时只生成 warning/list，不自动修复。
- 不修改 `.env.example` / `.env.production.example` 现有内容。
- 不读取本机真实 `.env` secret 值，不输出真实凭据。
- 如需修复，由运维按变更流程手动修改并复跑检查。

## 6. 验证建议

```bash
python -m pytest tests/test_config_drift_v332.py -q
python scripts/config_drift_check.py --output-dir .tmp_config_drift_check
```

验证后可手动清理 `.tmp_config_drift_check`。
