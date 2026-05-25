"use client";

import { useEffect, useMemo, useState } from "react";
import { callTool, listTools } from "@/lib/api/tools";
import type { ToolCallResult, ToolSpec } from "@/types/api";

function riskClass(riskLevel?: string): string {
  switch (riskLevel) {
    case "high":
      return "status-failed";
    case "medium":
      return "status-waiting_approval";
    case "low":
      return "status-completed";
    default:
      return "status-default";
  }
}

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolSpec[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [selectedToolName, setSelectedToolName] = useState("");
  const [argsText, setArgsText] = useState("{}");
  const [callResult, setCallResult] = useState<ToolCallResult | null>(null);
  const [callError, setCallError] = useState("");
  const [calling, setCalling] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErrorText("");
      try {
        const data = await listTools();
        if (cancelled) {
          return;
        }
        setTools(data);
        setSelectedToolName((prev) => prev || data[0]?.tool_name || "");
      } catch (error) {
        if (!cancelled) {
          setErrorText(error instanceof Error ? error.message : "工具列表加载失败");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredTools = useMemo(() => {
    return tools.filter((tool) => {
      const sourceOk = sourceFilter === "all" || tool.source === sourceFilter;
      const riskOk = riskFilter === "all" || tool.risk_level === riskFilter;
      return sourceOk && riskOk;
    });
  }, [tools, sourceFilter, riskFilter]);

  const sourceOptions = useMemo(() => {
    return ["all", ...Array.from(new Set(tools.map((tool) => tool.source))).sort()];
  }, [tools]);

  const riskOptions = useMemo(() => {
    return ["all", ...Array.from(new Set(tools.map((tool) => tool.risk_level))).sort()];
  }, [tools]);

  async function handleCallTool() {
    if (!selectedToolName) {
      setCallError("请先选择工具");
      return;
    }

    let parsedArgs: Record<string, unknown> = {};
    try {
      const raw = argsText.trim() || "{}";
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setCallError("arguments 必须是 JSON object");
        return;
      }
      parsedArgs = parsed as Record<string, unknown>;
    } catch {
      setCallError("arguments 不是合法 JSON");
      return;
    }

    setCalling(true);
    setCallError("");
    setCallResult(null);
    try {
      const result = await callTool(selectedToolName, parsedArgs);
      setCallResult(result);
    } catch (error) {
      setCallError(error instanceof Error ? error.message : "工具调用失败");
    } finally {
      setCalling(false);
    }
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">工具目录</h1>
        <p className="page-subtitle">展示当前可用工具并支持最小调用验证。默认走离线/本地路径，不接入真实外部 MCP。</p>
      </header>

      <section className="section card">
        <h2 className="card-title">筛选</h2>
        <div className="toolbar">
          <div>
            <label className="label" htmlFor="source_filter">
              source
            </label>
            <select
              id="source_filter"
              className="select"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
            >
              {sourceOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="risk_filter">
              risk_level
            </label>
            <select id="risk_filter" className="select" value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)}>
              {riskOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="section card">
        <h2 className="card-title">工具列表</h2>
        {loading ? (
          <div className="empty">工具列表加载中...</div>
        ) : errorText ? (
          <div className="empty">工具列表加载失败：{errorText}</div>
        ) : filteredTools.length === 0 ? (
          <div className="empty">当前筛选条件下无工具。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>name</th>
                  <th>description</th>
                  <th>source</th>
                  <th>risk_level</th>
                  <th>permission_scope</th>
                  <th>is_local</th>
                </tr>
              </thead>
              <tbody>
                {filteredTools.map((tool) => (
                  <tr key={`${tool.source}:${tool.tool_name}`}>
                    <td className="mono">{tool.tool_name}</td>
                    <td>{tool.description || "-"}</td>
                    <td className="mono">{tool.source}</td>
                    <td>
                      <span className={`badge ${riskClass(tool.risk_level)}`}>{tool.risk_level}</span>
                    </td>
                    <td className="mono">{tool.permission_scope || "-"}</td>
                    <td>{tool.is_local ? "true" : "false"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">工具调用（可选）</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          仅用于试点验证。高风险工具仍需遵循后端策略与审批流程，前端不会绕过策略引擎。
        </p>
        <div className="form-grid">
          <div>
            <label className="label" htmlFor="tool_name">
              tool_name
            </label>
            <select
              id="tool_name"
              className="select"
              value={selectedToolName}
              onChange={(e) => setSelectedToolName(e.target.value)}
              disabled={tools.length === 0}
            >
              {tools.length === 0 ? <option value="">无可用工具</option> : null}
              {tools.map((tool) => (
                <option key={`call-${tool.tool_name}`} value={tool.tool_name}>
                  {tool.tool_name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-grid-full">
            <label className="label" htmlFor="tool_arguments">
              arguments(JSON object)
            </label>
            <textarea
              id="tool_arguments"
              className="textarea"
              value={argsText}
              onChange={(e) => setArgsText(e.target.value)}
              spellCheck={false}
            />
          </div>
          <div className="form-grid-full">
            <button className="button" type="button" onClick={handleCallTool} disabled={calling}>
              {calling ? "调用中..." : "调用工具"}
            </button>
          </div>
          {callError ? <div className="form-grid-full muted">调用失败：{callError}</div> : null}
          {callResult ? (
            <div className="form-grid-full">
              <pre className="json-box">{JSON.stringify(callResult, null, 2)}</pre>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
