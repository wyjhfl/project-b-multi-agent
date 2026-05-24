# Release Checklist v1.0

## 发布前检查项

### 1. 测试全绿
- [ ] 370 个测试全部通过
- [ ] 无跳过、无预期失败

### 2. README 可跑通
- [ ] `python scripts/init_demo_db.py` 正常执行
- [ ] `uvicorn` 启动无报错
- [ ] `curl` 示例返回正确响应

### 3. Docker Compose 可启动
- [ ] `docker compose up --build` 正常构建并启动
- [ ] 各服务健康检查通过

### 4. API 文档完整
- [ ] `docs/api_v1.md` 已更新且与实际接口一致

### 5. Demo 脚本完整
- [ ] `docs/demo_script_v1.md` 可完整走通

### 6. 架构图完整
- [ ] `docs/architecture_v1.md` 已更新且与代码一致

### 7. 无密钥泄露
- [ ] `.env` 未提交到仓库
- [ ] `.gitignore` 包含 `.env` 及敏感文件规则
- [ ] 历史提交中无密钥残留

### 8. 默认 mock/fake 可运行
- [ ] `MCP_MODE=fake` 下项目可正常启动与测试
- [ ] `LLM_PROVIDER=fake` 下项目可正常启动与测试
- [ ] 无需任何真实 API Key 即可完成全流程

### 9. pyproject.toml version 更新
- [ ] `version` 字段已更新为 `1.0.0`

### 10. v1.0 tag 准备事项
- [ ] 创建 `v1.0.0` git tag
- [ ] 编写 Release Notes
- [ ] 确认 tag 对应提交通过 CI

---

## 后续 Roadmap

- 真实 MCP stdio 协议
- 真实 LangGraph checkpoint / interrupt
- 真实 LLM provider eval
- 前端审批 UI
- LLM-as-Judge 实接
- 长期记忆 / 向量库
- 持久化 Skill Learning
