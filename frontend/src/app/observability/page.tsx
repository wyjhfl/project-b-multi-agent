import Link from "next/link";
import { getTaskTrajectory } from "@/lib/api/observability";
import { getTaskTrace } from "@/lib/api/tasks";
import { formatDateTime } from "@/lib/status";
import type { TraceEvent, TrajectoryResponse } from "@/types/api";

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

function compactList(value: string[] | undefined): string {
  return value && value.length > 0 ? value.join(" / ") : "-";
}

function statusTone(value: string | undefined): string {
  const normalized = (value || "").toLowerCase();
  if (["completed", "success", "approved"].includes(normalized)) {
    return "success";
  }
  if (["failed", "rejected", "blocked"].includes(normalized)) {
    return "failed";
  }
  if (["waiting_approval", "running"].includes(normalized)) {
    return "waiting";
  }
  return "unknown";
}

function statusBadgeClass(value: string | undefined): string {
  const normalized = (value || "").toLowerCase();
  if (["completed", "success", "approved"].includes(normalized)) {
    return "status-completed";
  }
  if (["failed", "rejected", "blocked"].includes(normalized)) {
    return "status-failed";
  }
  if (normalized === "waiting_approval") {
    return "status-waiting_approval";
  }
  if (normalized === "running") {
    return "status-running";
  }
  return "status-default";
}

export default async function ObservabilityPage({ searchParams }: ObservabilityPageProps) {
  const params = (await searchParams) ?? {};
  const taskId = getTaskId(params.task_id);

  let events: TraceEvent[] = [];
  let trajectory: TrajectoryResponse | null = null;
  let traceError = "";
  let trajectoryError = "";

  if (taskId) {
    try {
      const [trace, trajectoryData] = await Promise.all([
        getTaskTrace(taskId),
        getTaskTrajectory(taskId),
      ]);
      events = trace.events || [];
      trajectory = trajectoryData;
    } catch (error) {
      traceError = error instanceof Error ? error.message : "Trace 查询失败";
      trajectoryError = error instanceof Error ? error.message : "Trajectory 查询失败";
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
        <h2 className="card-title">Multi-Agent 轨迹</h2>
        {!taskId ? (
          <div className="empty">请先输入 task_id 后查看角色轨迹。</div>
        ) : trajectoryError && !trajectory ? (
          <div className="empty">Trajectory 查询失败：{trajectoryError}</div>
        ) : !trajectory || trajectory.steps.length === 0 ? (
          <div className="empty">未查询到 Multi-Agent 轨迹。</div>
        ) : (
          <div className="trajectory-panel">
            <div className="trajectory-summary">
              <div>
                <div className="metric-label">是否 Multi-Agent</div>
                <div className="metric-value">{trajectory.summary.is_multi_agent ? "Yes" : "No"}</div>
              </div>
              <div>
                <div className="metric-label">角色链路</div>
                <div className="trajectory-value">{compactList(trajectory.summary.roles)}</div>
              </div>
              <div>
                <div className="metric-label">模式</div>
                <div className="trajectory-value">
                  {trajectory.summary.selected_mode || "-"} → {trajectory.summary.executed_mode || "-"}
                </div>
              </div>
              <div>
                <div className="metric-label">工具</div>
                <div className="trajectory-value">{compactList(trajectory.summary.tool_names)}</div>
              </div>
              <div>
                <div className="metric-label">Fallback / Approval</div>
                <div className="trajectory-value">
                  {trajectory.summary.fallback_used ? "fallback" : "no fallback"} /{" "}
                  {trajectory.summary.approval_required ? "approval" : "no approval"}
                </div>
              </div>
            </div>
            <div className="trajectory-steps">
              {trajectory.steps.map((step, index) => (
                <div className="trajectory-step" key={`${step.timestamp}-${step.event_type}-${index}`}>
                  <div className={`trajectory-index ${statusTone(step.status)}`}>{index + 1}</div>
                  <div className="trajectory-body">
                    <div className="trajectory-head">
                      <span className="trajectory-role">{step.role}</span>
                      <span className={`badge ${statusBadgeClass(step.status)}`}>{step.status || "recorded"}</span>
                      <span className="mono">{step.event_type}</span>
                    </div>
                    <div className="trajectory-meta">
                      action={step.action || "-"}
                      {step.selected_mode ? ` · selected=${step.selected_mode}` : ""}
                      {step.executed_mode ? ` · executed=${step.executed_mode}` : ""}
                      {step.approved !== null && step.approved !== undefined ? ` · approved=${String(step.approved)}` : ""}
                    </div>
                    {step.reason ? <div className="trajectory-reason">{step.reason}</div> : null}
                    {step.tool_names.length > 0 ? (
                      <div className="trajectory-tools">tools: {compactList(step.tool_names)}</div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
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
