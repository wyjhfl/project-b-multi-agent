import Link from "next/link";
import { listAuditEvents } from "@/lib/api/audit";
import { formatDateTime } from "@/lib/status";
import type { AuditEvent } from "@/types/api";

type AuditPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function pickSingle(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return raw[0]?.trim() || "";
  }
  return raw?.trim() || "";
}

function pickFilters(params: Record<string, string | string[] | undefined>) {
  const eventType = pickSingle(params.event_type);
  const taskId = pickSingle(params.task_id);
  const severity = pickSingle(params.severity);
  const outcome = pickSingle(params.outcome);
  return { eventType, taskId, severity, outcome };
}

export default async function AuditPage({ searchParams }: AuditPageProps) {
  const params = (await searchParams) ?? {};
  const { eventType, taskId, severity, outcome } = pickFilters(params);

  let events: AuditEvent[] = [];
  let errorText = "";
  try {
    events = await listAuditEvents({
      event_type: eventType || undefined,
      task_id: taskId || undefined,
      severity: severity || undefined,
      outcome: outcome || undefined,
      limit: 100,
    });
  } catch (error) {
    errorText = error instanceof Error ? error.message : "审计事件加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">审计事件</h1>
        <p className="page-subtitle">按 event_type / task_id / severity / outcome 筛选审计留痕。</p>
      </header>

      <section className="section card">
        <h2 className="card-title">筛选条件</h2>
        <form method="get" className="form-grid">
          <div>
            <label htmlFor="event_type" className="label">
              event_type
            </label>
            <input id="event_type" name="event_type" className="input" defaultValue={eventType} />
          </div>
          <div>
            <label htmlFor="task_id" className="label">
              task_id
            </label>
            <input id="task_id" name="task_id" className="input" defaultValue={taskId} />
          </div>
          <div>
            <label htmlFor="severity" className="label">
              severity
            </label>
            <input id="severity" name="severity" className="input" defaultValue={severity} />
          </div>
          <div>
            <label htmlFor="outcome" className="label">
              outcome
            </label>
            <input id="outcome" name="outcome" className="input" defaultValue={outcome} />
          </div>
          <div className="form-grid-full toolbar">
            <button type="submit" className="button">
              查询审计
            </button>
            <Link href="/audit" className="button secondary">
              重置
            </Link>
          </div>
        </form>
      </section>

      <section className="section card">
        <h2 className="card-title">审计列表</h2>
        {errorText ? (
          <div className="empty">审计事件加载失败：{errorText}</div>
        ) : events.length === 0 ? (
          <div className="empty">未查询到审计事件。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>event_id</th>
                  <th>event_type</th>
                  <th>task_id</th>
                  <th>action</th>
                  <th>outcome</th>
                  <th>severity</th>
                  <th>timestamp</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.event_id}>
                    <td className="mono">{event.event_id}</td>
                    <td className="mono">{event.event_type}</td>
                    <td className="mono">{event.task_id || "-"}</td>
                    <td>{event.action || "-"}</td>
                    <td>{event.outcome || "-"}</td>
                    <td>{event.severity || "-"}</td>
                    <td>{formatDateTime(event.timestamp)}</td>
                    <td>
                      <Link className="button secondary" href={`/audit/${event.event_id}`}>
                        查看详情
                      </Link>
                    </td>
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
