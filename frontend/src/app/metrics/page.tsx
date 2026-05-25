import Link from "next/link";
import { getRuntimeSummary } from "@/lib/api/metrics";

export default async function MetricsPage() {
  let runtime = null;
  let error = "";
  try {
    runtime = await getRuntimeSummary();
  } catch (e) {
    error = e instanceof Error ? e.message : "指标加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">指标入口（占位）</h1>
        <p className="page-subtitle">
          v2.4.1 仅提供最小指标入口，复杂图表和 BI 看板将在后续阶段逐步补齐。
        </p>
      </header>

      <section className="section card">
        <h2 className="card-title">运行时摘要</h2>
        {error ? (
          <div className="empty">指标加载失败：{error}</div>
        ) : (
          <pre className="json-box">{JSON.stringify(runtime, null, 2)}</pre>
        )}
      </section>

      <section className="section card">
        <div className="toolbar">
          <Link className="button secondary" href="/">
            返回 Dashboard
          </Link>
          <Link className="button secondary" href="/tasks">
            返回任务中心
          </Link>
        </div>
      </section>
    </div>
  );
}
