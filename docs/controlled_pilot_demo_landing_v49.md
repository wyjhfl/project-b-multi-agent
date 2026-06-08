# 无真实业务系统受控试点落地入口

## 适用场景

当前没有真实业务系统时，先使用 `demo read-only` 路径完成本地和内网受控试点证据链。该路径的目标是证明 Project B 的只读业务接入链路、门禁、审计边界、运行包和证据归档可以串起来，输出范围仅限 `controlled internal pilot`。

该路径不等于真实业务系统生产验收完成，也不代表公网生产可以直接上线。输出中必须保持 `public_production_direct_launch=No-Go` 的边界。`controlled_internal_pilot` 有两种正常状态：证据全部满足时为 `Go`；当前工作区、证据 freshness 或剩余缺口仍需人工复核时为 `Manual-Review`。

## 执行命令

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_demo_landing.ps1
```

如需使用本地 ignored 配置文件中的非敏感演示参数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\controlled_pilot_demo_landing.ps1 -EnvPath local\production_landing.staging.env
```

不要在命令行、文档或报告中填写真实密钥、真实连接串或真实凭据。

## 执行链路

脚本会按顺序刷新以下证据：

- demo 业务只读 smoke：`docs/reports/business_system_read_smoke/`
- 业务系统 landing resume 证据链：`business_system_landing_resume.ps1`
- 受控试点 delivery gate：`docs/reports/controlled_pilot_delivery_gate/`
- 受控试点运行包：`docs/reports/controlled_pilot_run_packet/`
- 证据归档 manifest：`docs/reports/evidence_archive/`
- 文本质量检查：`docs/reports/production_landing_text_quality/`

正常结束时，终端会输出：

```text
[controlled_pilot_demo_landing] controlled_internal_pilot=Go
[controlled_pilot_demo_landing] missing_condition_count=0
[controlled_pilot_demo_landing] public_production_direct_launch=No-Go
[controlled_pilot_demo_landing] status=done
```

如果当前工作区未提交、证据 freshness 仍需要人工复核，脚本也可能如实输出：

```text
[controlled_pilot_demo_landing] controlled_internal_pilot=Manual-Review
[controlled_pilot_demo_landing] missing_condition_count=2
[controlled_pilot_demo_landing] missing_condition=controlled_pilot_operator_packet:production_landing_evidence_freshness:not_fresh
[controlled_pilot_demo_landing] missing_condition=controlled_pilot_run_packet:required_ready_evidence_not_satisfied
[controlled_pilot_demo_landing] public_production_direct_launch=No-Go
[controlled_pilot_demo_landing] status=done
```

`Manual-Review` 不是失败，也不是公网生产 Go；它表示 demo read-only 证据链已经刷新，但还需要人工复核当前工作区、证据 freshness 或剩余缺口。

## 真实生产缺口

因为当前没有真实业务系统，受控试点运行包会继续保留 `business_system:real_business_system_required`。该缺口只允许作为内网受控试点的已接受剩余缺口，不能用于真实生产验收。

后续要进入真实业务系统验收，至少需要准备：

- 真实业务系统 base URL
- 真实只读 token 或等价只读凭据
- 只读探测路径与工具白名单
- 业务 owner、安全 reviewer、运维 owner、数据 owner
- 只读审计证据、失败恢复证据和回滚证据

拿到这些信息后，应改走真实只读 smoke 与真实业务系统 readiness gate，并重新进行人工 Go/No-Go 复核。
