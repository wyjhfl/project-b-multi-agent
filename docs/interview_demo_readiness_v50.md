# 面试演示就绪检查 v5.0

## 目标

`scripts\interview_demo_readiness.py` 用于面试前只读自检，确认当前项目具备可写入简历、可现场演示、可解释边界的基本材料。

该脚本不会启动服务、不会连接真实业务系统、不会读取 `.env`、不会调用真实 LLM、不会写业务数据。它只读取仓库内的文档、前端源码和演示脚本存在性，并输出 JSON 与 Markdown 报告。

## 推荐命令

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\codex_python.ps1 scripts\interview_demo_readiness.py
```

默认输出目录：

```text
docs/reports/interview_demo_readiness/
```

## 检查范围

- 简历材料：`docs/resume_interview_optimization_pack_v50.md`、`docs/resume_blog_notes.md`、`docs/interview_guide.md`。
- 演示入口：Operations Command Center、Operator Guidance、Review Reasons、No-Go 边界。
- 演示脚本：`scripts\controlled_pilot_demo_landing.ps1`、`scripts\controlled_pilot_console_up.ps1`、`scripts\production_landing_text_quality_check.py`。
- 安全边界：`public_production_direct_launch=No-Go`、`real_business_system_connected=false`、`business_data_written=false`、`secret_plaintext_output=false`。

## 面试使用方式

1. 先运行 interview demo readiness，确认简历材料和演示入口都存在。
2. 再运行 controlled pilot demo landing，生成受控试点证据。
3. 启动 Operations Command Center，打开 `/operations`。
4. 面试演示时先讲架构，再展示 Landing Command Center、Evidence Chain、Review Reasons、Operator Guidance。

## 口径边界

- 当前没有真实业务系统时，只展示 demo read-only 受控试点路径。
- 不宣称公网生产可直接上线。
- 不宣称真实业务系统生产验收完成。
- 不宣称完全自治多 Agent；当前是确定性多角色编排。
- 不输出任何 API key、token、连接串或 prompt 原文。
