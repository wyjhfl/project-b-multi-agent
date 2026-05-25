"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createTask } from "@/lib/api/tasks";

export default function TaskCreatePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("keyword");
  const [generator, setGenerator] = useState("mock");
  const [provider, setProvider] = useState("");
  const [fallbackToMock, setFallbackToMock] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      setError("查询内容不能为空");
      return;
    }

    setSubmitting(true);
    setError("");
    try {
      const result = await createTask({
        query: query.trim(),
        mode,
        generator,
        provider: provider.trim() || undefined,
        fallback_to_mock: fallbackToMock,
      });
      router.push(`/tasks/${result.task_id}?created=1`);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <header className="toolbar" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">新建任务</h1>
          <p className="page-subtitle">创建一个离线可运行的任务，并跳转到详情页查看结果与 Trace。</p>
        </div>
        <Link className="button secondary" href="/tasks">
          返回任务列表
        </Link>
      </header>

      <section className="section card">
        <h2 className="card-title">任务参数</h2>
        <form onSubmit={onSubmit} className="form-grid">
          <div className="form-grid-full">
            <label className="label" htmlFor="query">
              查询内容
            </label>
            <textarea
              id="query"
              name="query"
              className="textarea"
              placeholder="例如：今天 GMV 是多少？"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="label" htmlFor="mode">
              执行模式
            </label>
            <select
              id="mode"
              name="mode"
              className="select"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="keyword">keyword</option>
              <option value="nl2sql">nl2sql</option>
              <option value="multitool">multitool</option>
              <option value="multi_agent">multi_agent</option>
              <option value="auto">auto</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="generator">
              生成器
            </label>
            <select
              id="generator"
              name="generator"
              className="select"
              value={generator}
              onChange={(e) => setGenerator(e.target.value)}
            >
              <option value="mock">mock</option>
              <option value="llm">llm</option>
            </select>
          </div>

          <div>
            <label className="label" htmlFor="provider">
              Provider（可选）
            </label>
            <input
              id="provider"
              name="provider"
              className="input"
              placeholder="fake / litellm"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            />
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              id="fallback_to_mock"
              name="fallback_to_mock"
              type="checkbox"
              checked={fallbackToMock}
              onChange={(e) => setFallbackToMock(e.target.checked)}
            />
            <label htmlFor="fallback_to_mock" className="muted">
              启用 fallback_to_mock
            </label>
          </div>

          {error ? <div className="form-grid-full muted">提交失败：{error}</div> : null}

          <div className="form-grid-full">
            <button className="button" type="submit" disabled={submitting}>
              {submitting ? "提交中..." : "创建任务"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
