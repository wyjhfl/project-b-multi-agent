import Link from "next/link";
import { getOperationsSummary } from "@/lib/api/operations";
import { formatDateTime } from "@/lib/status";

function boolLabel(value: boolean): string {
  return value ? "Yes" : "No";
}

function compactJson(value: unknown): string {
  try {
    const text = JSON.stringify(value ?? {});
    if (text.length <= 180) {
      return text;
    }
    return `${text.slice(0, 180)}...`;
  } catch {
    return String(value ?? "");
  }
}

export default async function OperationsOverviewPage() {
  let summary: Awaited<ReturnType<typeof getOperationsSummary>> | null = null;
  let errorText = "";

  try {
    summary = await getOperationsSummary();
  } catch (error) {
    errorText = error instanceof Error ? error.message : "failed to load operations overview";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">Operations Overview (Read Only)</h1>
        <p className="page-subtitle">
          Read-only observability panel for health / deployment / metrics / tasks / approvals / audit / pilot reports /
          demo evidence. Default fake/offline. No real LLM call. No secrets.
        </p>
      </header>

      {errorText ? (
        <section className="section card">
          <div className="empty">service unavailable: {errorText}</div>
          <div className="mono muted path-break">hint: start backend service and retry /operations</div>
        </section>
      ) : !summary ? (
        <section className="section card">
          <div className="empty">no summary data available</div>
        </section>
      ) : (
        <>
          <section className="section card">
            <h2 className="card-title">Boundary & mode</h2>
            <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
              <li>read-only surface, no write/delete actions</li>
              <li>default fake/offline path, no real external LLM call from this page</li>
              <li>sanitized output only, no prompt raw text or secret plaintext</li>
            </ul>
          </section>

          <section className="section">
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">health.status</div>
                <div className="metric-value">{summary.health.status || "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">version</div>
                <div className="metric-value">{summary.health.version || "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">deployment.ok</div>
                <div className="metric-value">{boolLabel(summary.deployment.ok)}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">tasks</div>
                <div className="metric-value">{summary.task_approval.task_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pending approvals</div>
                <div className="metric-value">{summary.task_approval.pending_approval_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">recent audit events</div>
                <div className="metric-value">{summary.audit.event_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pilot reports</div>
                <div className="metric-value">{summary.pilot_reports.total_reports}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">runtime cost</div>
                <div className="metric-value">{summary.runtime_metrics.total_cost?.toFixed?.(4) ?? "-"}</div>
              </div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">Deployment check</h2>
            <div className="mono path-break">
              env={summary.deployment.environment || "-"} checks={summary.deployment.check_count} errors=
              {summary.deployment.error_count} warnings={summary.deployment.warning_count}
            </div>
            {summary.deployment.error_count > 0 ? (
              <div className="empty path-break">error: {summary.deployment.errors.join(" | ")}</div>
            ) : (
              <div className="empty">no deployment errors</div>
            )}
            {summary.deployment.warning_count > 0 ? (
              <div className="empty path-break">warning: {summary.deployment.warnings.join(" | ")}</div>
            ) : (
              <div className="empty">no deployment warnings</div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Runtime metrics summary</h2>
            <div className="stack">
              <div className="mono path-break">
                tasks={summary.runtime_metrics.task_count ?? 0} success={summary.runtime_metrics.success_count ?? 0} failed=
                {summary.runtime_metrics.failed_count ?? 0} waiting={summary.runtime_metrics.waiting_approval_count ?? 0}
              </div>
              <div className="mono path-break">
                prompt_tokens={summary.runtime_metrics.total_prompt_tokens ?? 0} completion_tokens=
                {summary.runtime_metrics.total_completion_tokens ?? 0} total_cost={summary.runtime_metrics.total_cost ?? 0}
              </div>
              <div className="mono path-break">llm_budget={compactJson(summary.runtime_metrics.llm_budget)}</div>
              <div className="mono path-break">llm_cache={compactJson(summary.runtime_metrics.llm_cache)}</div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">Tasks / approvals (recent)</h2>
            <div className="mono path-break">task_status_counts={compactJson(summary.task_approval.task_status_counts)}</div>
            {summary.task_approval.recent_tasks.length === 0 ? (
              <div className="empty">no tasks</div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>task_id</th>
                      <th>status</th>
                      <th>mode</th>
                      <th>created_at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.task_approval.recent_tasks.map((item) => (
                      <tr key={item.task_id}>
                        <td className="mono path-break">{item.task_id}</td>
                        <td>{item.status || "-"}</td>
                        <td>{item.mode || "-"}</td>
                        <td>{formatDateTime(item.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Audit events (sanitized)</h2>
            {summary.audit.recent_events.length === 0 ? (
              <div className="empty">no audit events</div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>event_id</th>
                      <th>event_type</th>
                      <th>outcome</th>
                      <th>request_id</th>
                      <th>summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.audit.recent_events.map((event) => (
                      <tr key={event.event_id}>
                        <td className="mono path-break">{event.event_id}</td>
                        <td>{event.event_type}</td>
                        <td>{event.outcome || "-"}</td>
                        <td className="mono path-break">{event.request_id || "-"}</td>
                        <td>{event.summary || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Pilot reports / demo evidence</h2>
            <div className="mono path-break">
              directory_exists={String(summary.pilot_reports.directory_exists)} report_dir={summary.pilot_reports.report_dir}
            </div>

            {!summary.pilot_reports.directory_exists ? (
              <div className="empty">no reports directory</div>
            ) : summary.pilot_reports.reports.length === 0 ? (
              <div className="empty">no reports</div>
            ) : (
              <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
                {summary.pilot_reports.reports.map((item) => (
                  <li key={item.report_id}>
                    <div className="mono path-break">
                      {item.generated_at} | {item.scenario} | {item.outcome} | request_id={item.request_id || "<empty>"}
                    </div>
                    <div className="mono path-break">
                      fallback={String(item.fallback_used)} cost={item.cost} tokens={item.total_tokens} audit_event_id=
                      {item.audit_event_id || "<empty>"}
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="empty path-break">demo_e2e tip: {summary.demo_evidence.tip}</div>

            <div className="stack">
              <div className="mono path-break">demo_runbook={summary.demo_evidence.runbook_path}</div>
              <div className="mono path-break">demo_script={summary.demo_evidence.script_path}</div>
              <div className="mono path-break">
                acceptance_snapshot_runbook={summary.observability.acceptance_snapshot_runbook_path}
              </div>
              <div className="mono path-break">
                demo_artifact_runbook={summary.observability.demo_artifact_runbook_path}
              </div>
              <div className="mono path-break">
                artifact_default_dir={summary.observability.artifact_default_dir}
              </div>
              <div className="mono path-break">
                snapshot_default_dir={summary.observability.snapshot_default_dir}
              </div>
              <div className="mono path-break">
                last_known_counts={compactJson(summary.observability.last_known_report_counts)}
              </div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">Acceptance / demo status hints</h2>
            {summary.runtime_metrics.llm_budget && compactJson(summary.runtime_metrics.llm_budget).includes("skipped") ? (
              <div className="empty">runtime includes skipped signals in budget summary</div>
            ) : (
              <div className="empty">no explicit skipped signal from runtime budget summary</div>
            )}
            {!summary.pilot_reports.directory_exists || summary.pilot_reports.total_reports === 0 ? (
              <div className="empty">pilot evidence currently empty; run demo_e2e or acceptance snapshot for fresh artifacts</div>
            ) : null}
          </section>

          <section className="section card">
            <div className="toolbar">
              <Link className="button secondary" href="/llm">
                View LLM Pilot
              </Link>
              <Link className="button secondary" href="/audit">
                View Audit
              </Link>
              <Link className="button secondary" href="/metrics">
                View Metrics
              </Link>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
