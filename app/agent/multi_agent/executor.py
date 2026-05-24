from __future__ import annotations

from typing import Any

from app.agent.multi_agent.types import AgentDecision


class ExecutorAgent:
    def __init__(
        self,
        nl2sql_pipeline: Any | None = None,
        multitool_pipeline: Any | None = None,
        tool_gateway: Any | None = None,
        policy_engine: Any | None = None,
        planner: Any | None = None,
    ) -> None:
        self._nl2sql_pipeline = nl2sql_pipeline
        self._multitool_pipeline = multitool_pipeline
        self._tool_gateway = tool_gateway
        self._policy_engine = policy_engine
        self._planner = planner

    def execute(
        self,
        query: str,
        selected_mode: str,
        generator: str = "mock",
        provider: str | None = None,
        fallback_to_mock: bool = True,
        task_id: str | None = None,
    ) -> tuple[dict[str, Any], AgentDecision]:
        if selected_mode == "nl2sql":
            return self._execute_nl2sql(query, generator, provider, fallback_to_mock)
        elif selected_mode == "multitool":
            return self._execute_multitool(query, task_id)
        elif selected_mode == "keyword":
            return self._execute_keyword(query)
        else:
            return self._execute_auto(query, generator, provider, fallback_to_mock, task_id)

    def _execute_nl2sql(
        self,
        query: str,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
    ) -> tuple[dict[str, Any], AgentDecision]:
        if self._nl2sql_pipeline is None:
            from app.services.nl2sql_pipeline import NL2SQLPipeline
            self._nl2sql_pipeline = NL2SQLPipeline()

        result = self._nl2sql_pipeline.run(
            query=query,
            generator=generator,
            provider=provider,
            fallback_to_mock=fallback_to_mock,
        )
        decision = AgentDecision(
            role="executor",
            action="execute_nl2sql",
            reason=f"NL2SQL 执行 {'成功' if result['success'] else '失败'}",
            confidence=0.9 if result["success"] else 0.5,
            metadata={"selected_mode": "nl2sql"},
        )
        return result, decision

    def _execute_multitool(
        self,
        query: str,
        task_id: str | None,
    ) -> tuple[dict[str, Any], AgentDecision]:
        if self._multitool_pipeline is None:
            from app.services.multitool_pipeline import MultiToolPipeline
            self._multitool_pipeline = MultiToolPipeline(
                self._tool_gateway,
                policy_engine=self._policy_engine,
            )

        result = self._multitool_pipeline.run(query=query, task_id=task_id)
        decision = AgentDecision(
            role="executor",
            action="execute_multitool",
            reason=f"MultiTool 执行 {'成功' if result['success'] else '失败'}",
            confidence=0.9 if result["success"] else 0.5,
            metadata={"selected_mode": "multitool"},
        )
        return result, decision

    def _execute_keyword(
        self,
        query: str,
    ) -> tuple[dict[str, Any], AgentDecision]:
        if self._planner is None:
            from app.agent.nodes.planner import KeywordPlanner
            self._planner = KeywordPlanner()

        plan_result = self._planner.plan(query)
        policy_blocked = False

        if not plan_result.get("matched"):
            result = {
                "mode": "keyword",
                "success": False,
                "answer": "未匹配关键词",
            }
        else:
            tool_name = plan_result.get("tool_name")
            if tool_name and self._tool_gateway:
                spec = self._tool_gateway.get_tool(tool_name)
                if spec and self._policy_engine:
                    policy_decision = self._policy_engine.evaluate(tool_name, risk_level=spec.risk_level)
                    if not policy_decision["allowed"]:
                        policy_blocked = True
                        result = {
                            "mode": "keyword",
                            "success": False,
                            "answer": f"工具调用被策略拦截: {policy_decision['reason']}",
                            "tool_called": tool_name,
                            "error_type": "policy_blocked",
                            "blocked": True,
                        }
                        decision = AgentDecision(
                            role="executor",
                            action="execute_keyword",
                            reason=f"Keyword 执行失败: 策略拦截",
                            confidence=0.3,
                            metadata={"selected_mode": "keyword", "policy_blocked": True},
                        )
                        return result, decision

                record = self._tool_gateway.call(tool_name)
                if record.success:
                    label = self._planner.get_label(tool_name)
                    result = {
                        "mode": "keyword",
                        "success": True,
                        "answer": f"{label}查询结果：{record.result}",
                        "data": record.result,
                        "tool_called": tool_name,
                    }
                else:
                    result = {
                        "mode": "keyword",
                        "success": False,
                        "answer": f"工具调用失败: {record.error}",
                        "tool_called": tool_name,
                    }
            else:
                result = {
                    "mode": "keyword",
                    "success": False,
                    "answer": "无可用工具",
                }

        decision = AgentDecision(
            role="executor",
            action="execute_keyword",
            reason=f"Keyword 执行 {'成功' if result['success'] else '失败'}",
            confidence=0.9 if result["success"] else 0.5,
            metadata={"selected_mode": "keyword", "policy_blocked": policy_blocked},
        )
        return result, decision

    def _execute_auto(
        self,
        query: str,
        generator: str,
        provider: str | None,
        fallback_to_mock: bool,
        task_id: str | None,
    ) -> tuple[dict[str, Any], AgentDecision]:
        fallback_chain: list[str] = []

        result, _ = self._execute_nl2sql(query, generator, provider, fallback_to_mock)
        fallback_chain.append("nl2sql")
        if result["success"]:
            result["executed_mode"] = "nl2sql"
            result["fallback_chain"] = fallback_chain
            decision = AgentDecision(
                role="executor",
                action="execute_auto",
                reason="Auto 模式: NL2SQL 成功",
                confidence=0.9,
                metadata={"selected_mode": "auto", "executed_mode": "nl2sql"},
            )
            return result, decision

        result_mt, _ = self._execute_multitool(query, task_id)
        fallback_chain.append("multitool")
        if result_mt["success"]:
            result_mt["executed_mode"] = "multitool"
            result_mt["fallback_chain"] = fallback_chain
            decision = AgentDecision(
                role="executor",
                action="execute_auto",
                reason="Auto 模式: NL2SQL 失败，Multitool 成功",
                confidence=0.7,
                metadata={"selected_mode": "auto", "executed_mode": "multitool"},
            )
            return result_mt, decision

        result_kw, _ = self._execute_keyword(query)
        fallback_chain.append("keyword")
        result_kw["executed_mode"] = "keyword"
        result_kw["fallback_chain"] = fallback_chain
        decision = AgentDecision(
            role="executor",
            action="execute_auto",
            reason="Auto 模式: NL2SQL 和 Multitool 均失败，Keyword fallback",
            confidence=0.5,
            metadata={"selected_mode": "auto", "executed_mode": "keyword"},
        )
        return result_kw, decision
