"use client";

import { FormEvent, useRef, useState } from "react";
import { executeNl2sql, previewNl2sql, streamNl2sql } from "@/lib/api/nl2sql";
import type { NL2SQLExecuteResult, NL2SQLPreviewResult } from "@/types/api";

function renderRows(result: NL2SQLExecuteResult | null) {
  const rows = result?.execution?.rows || result?.formatted_result?.rows;
  if (!Array.isArray(rows) || rows.length === 0) {
    return <div className="empty">无结果行数据。</div>;
  }
  return <pre className="json-box">{JSON.stringify(rows, null, 2)}</pre>;
}

export default function Nl2sqlPage() {
  const [query, setQuery] = useState("");
  const [generator, setGenerator] = useState("mock");
  const [provider, setProvider] = useState("fake");
  const [mode, setMode] = useState("nl2sql");
  const [fallbackToMock, setFallbackToMock] = useState(true);
  const [previewResult, setPreviewResult] = useState<NL2SQLPreviewResult | null>(null);
  const [executeResult, setExecuteResult] = useState<NL2SQLExecuteResult | null>(null);
  const [errorText, setErrorText] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [loadingExecute, setLoadingExecute] = useState(false);
  const [loadingStream, setLoadingStream] = useState(false);
  const [streamStages, setStreamStages] = useState<string[]>([]);
  const [streamSql, setStreamSql] = useState("");
  const [streamGuard, setStreamGuard] = useState<{ allowed: boolean; reason: string } | null>(null);
  const [streamResult, setStreamResult] = useState<NL2SQLExecuteResult | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);

  async function onPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      setErrorText("query 不能为空");
      return;
    }
    setLoadingPreview(true);
    setErrorText("");
    setExecuteResult(null);
    try {
      const result = await previewNl2sql({
        query: query.trim(),
        generator,
        provider: provider.trim() || undefined,
        fallback_to_mock: fallbackToMock,
      });
      setPreviewResult(result);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "预览失败");
    } finally {
      setLoadingPreview(false);
    }
  }

  async function onExecute() {
    if (!query.trim()) {
      setErrorText("query 不能为空");
      return;
    }
    setLoadingExecute(true);
    setErrorText("");
    try {
      const result = await executeNl2sql({
        query: query.trim(),
        generator,
        provider: provider.trim() || undefined,
        fallback_to_mock: fallbackToMock,
      });
      setExecuteResult(result);
      if (!previewResult) {
        setPreviewResult(result);
      }
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : "执行失败");
    } finally {
      setLoadingExecute(false);
    }
  }

  async function onStream() {
    if (!query.trim()) {
      setErrorText("query 不能为空");
      return;
    }
    streamAbortRef.current?.abort();
    const controller = new AbortController();
    streamAbortRef.current = controller;
    setLoadingStream(true);
    setErrorText("");
    setStreamStages([]);
    setStreamSql("");
    setStreamGuard(null);
    setStreamResult(null);
    try {
      await streamNl2sql(
        {
          query: query.trim(),
          generator,
          provider: provider.trim() || undefined,
          fallback_to_mock: fallbackToMock,
        },
        {
          onStage: (stage) => setStreamStages((prev) => [...prev, stage]),
          onSqlDelta: (delta) => setStreamSql((prev) => prev + delta),
          onGuard: (allowed, reason) => setStreamGuard({ allowed, reason }),
          onDone: (result) => setStreamResult(result),
          onError: (reason) => setErrorText(reason),
        },
        controller.signal,
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setErrorText(error instanceof Error ? error.message : "流式生成失败");
      }
    } finally {
      setLoadingStream(false);
    }
  }

  function onStopStream() {
    streamAbortRef.current?.abort();
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">NL2SQL 试点页</h1>
        <p className="page-subtitle">
          默认走离线 mock/fake 路径。页面仅展示后端返回结果，不展示任何原始 PII 文本。
        </p>
      </header>

      <section className="section card">
        <h2 className="card-title">查询与参数</h2>
        <form onSubmit={onPreview} className="form-grid">
          <div className="form-grid-full">
            <label className="label" htmlFor="query">
              query
            </label>
            <textarea
              id="query"
              className="textarea"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="例如：最近 7 天订单量和 GMV"
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="mode">
              mode（显示用途）
            </label>
            <select id="mode" className="select" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="nl2sql">nl2sql</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="generator">
              generator
            </label>
            <select id="generator" className="select" value={generator} onChange={(e) => setGenerator(e.target.value)}>
              <option value="mock">mock</option>
              <option value="llm">llm</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="provider">
              provider
            </label>
            <select id="provider" className="select" value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="fake">fake</option>
              <option value="litellm">litellm</option>
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              id="fallback_to_mock"
              type="checkbox"
              checked={fallbackToMock}
              onChange={(e) => setFallbackToMock(e.target.checked)}
            />
            <label htmlFor="fallback_to_mock" className="muted">
              fallback_to_mock
            </label>
          </div>

          <div className="form-grid-full toolbar">
            <button className="button" type="submit" disabled={loadingPreview}>
              {loadingPreview ? "预览中..." : "Preview"}
            </button>
            <button className="button secondary" type="button" onClick={onExecute} disabled={loadingExecute}>
              {loadingExecute ? "执行中..." : "Execute"}
            </button>
            <button className="button secondary" type="button" onClick={onStream} disabled={loadingStream}>
              {loadingStream ? "流式生成中..." : "Stream"}
            </button>
            {loadingStream ? (
              <button className="button secondary" type="button" onClick={onStopStream}>
                停止
              </button>
            ) : null}
          </div>
        </form>
        {errorText ? <div className="empty">请求失败：{errorText}</div> : null}
      </section>

      <section className="section card">
        <h2 className="card-title">流式生成</h2>
        {streamStages.length > 0 || streamSql || streamGuard || streamResult ? (
          <div className="stack">
            <div className="toolbar">
              {streamStages.map((stage) => (
                <span key={stage} className="badge status-default">
                  {stage}
                </span>
              ))}
              {streamGuard ? (
                <span className={`badge ${streamGuard.allowed ? "status-completed" : "status-failed"}`}>
                  guard_allowed: {String(streamGuard.allowed)}
                </span>
              ) : null}
              {loadingStream ? <span className="badge status-default">streaming...</span> : null}
            </div>
            {streamGuard && !streamGuard.allowed ? (
              <div className="empty">guard 拦截：{streamGuard.reason}</div>
            ) : null}
            <pre className="json-box">{streamSql || "(SQL 增量输出中...)"}</pre>
            {streamResult ? <pre className="json-box">{JSON.stringify(streamResult, null, 2)}</pre> : null}
          </div>
        ) : (
          <div className="empty">点击 Stream 查看逐 chunk 生成过程。</div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">Preview 结果</h2>
        {previewResult ? (
          <div className="stack">
            <div className="toolbar">
              <span className={`badge ${previewResult.guard_allowed ? "status-completed" : "status-failed"}`}>
                guard_allowed: {String(previewResult.guard_allowed)}
              </span>
              <span className="badge status-default">confidence: {previewResult.confidence.toFixed(2)}</span>
              <span className="badge status-default">fallback_used: {String(previewResult.fallback_used)}</span>
            </div>
            <pre className="json-box">{JSON.stringify(previewResult, null, 2)}</pre>
          </div>
        ) : (
          <div className="empty">请先执行 Preview。</div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">Execute 结果</h2>
        {executeResult ? (
          <div className="stack">
            <div className="toolbar">
              <span className={`badge ${executeResult.execution?.success ? "status-completed" : "status-failed"}`}>
                execution_success: {String(Boolean(executeResult.execution?.success))}
              </span>
              <span className="badge status-default">rows: {executeResult.execution?.row_count ?? 0}</span>
            </div>
            <pre className="json-box">{JSON.stringify(executeResult, null, 2)}</pre>
            <h3 style={{ margin: "4px 0 0", fontSize: 14 }}>rows/result</h3>
            {renderRows(executeResult)}
          </div>
        ) : (
          <div className="empty">请执行 Execute 查看结果。</div>
        )}
      </section>
    </div>
  );
}
