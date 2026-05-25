import Link from "next/link";
import { getTaskTrace } from "@/lib/api/tasks";
import { formatDateTime } from "@/lib/status";
import type { TraceEvent } from "@/types/api";

type ObservabilityPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function getTaskId(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return raw[0]?.trim() || "";
  }
  return raw?.trim() || "";
}

function compactJson(value: unknown): string {
  try {
    const text = JSON.stringify(value ?? {});
    if (text.length <= 140) {
      return text;
    }
    return `${text.slice(0, 140)}...`;
  } catch {
    return String(value ?? "");
  }
}

export default async function ObservabilityPage({ searchParams }: ObservabilityPageProps) {
  const params = (await searchParams) ?? {};
  const taskId = getTaskId(params.task_id);

  let events: TraceEvent[] = [];
  let traceError = "";

  if (taskId) {
    try {
      const trace = await getTaskTrace(taskId);
      events = trace.events || [];
    } catch (error) {
      traceError = error instanceof Error ? error.message : "Trace 查询失败";
    }
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">追踪审计</h1>
        <p className="page-subtitle">按 task_id 查询执行 Trace 时间线，并跳转审计事件列表。</p>
      </header>

      <section className="section card">
        <h2 className="card-title">Trace 查询</h2>
        <form method="get" className="toolbar">
          <input
            name="task_id"
            className="input"
            defaultValue={taskId}
            placeholder="输入 task_id，例如 8f2a..."
            style={{ maxWidth: 460 }}
          />
          <button type="submit" className="button">
            查询 Trace
          </button>
          <Link className="button secondary" href="/audit">
            查看审计事件
          </Link>
        </form>
      </section>

      <section className="section card">
        <h2 className="card-title">Trace 时间线</h2>
        {!taskId ? (
          <div className="empty">请先输入 task_id 后查询。</div>
        ) : traceError ? (
          <div className="empty">Trace 查询失败：{traceError}</div>
        ) : events.length === 0 ? (
          <div className="empty">未查询到 Trace 事件。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>事件类型</th>
                  <th>执行者</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.event_id || `${event.timestamp}-${event.event_type}`}>
                    <td>{formatDateTime(event.timestamp)}</td>
                    <td className="mono">{event.event_type}</td>
                    <td>{event.actor || "-"}</td>
                    <td className="mono">{compactJson(event.detail)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
