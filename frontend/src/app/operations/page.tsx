import Link from "next/link";
import { getOperationsSummary } from "@/lib/api/operations";
import { formatDateTime } from "@/lib/status";

function boolLabel(value: boolean): string {
  return value ? "是" : "否";
}

function compactJson(value: unknown): string {
  try {
    const text = JSON.stringify(value ?? {});
    if (text.length <= 160) {
      return text;
    }
    return `${text.slice(0, 160)}...`;
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
    errorText = error instanceof Error ? error.message : "运营总览加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">运营总览（只读）</h1>
        <p className="page-subtitle">
          汇总 health、deployment、metrics、tasks/approvals、audit、pilot evidence。仅展示脱敏摘要，不提供写操作。
        </p>
      </header>

      {errorText ? (
        <section className="section card">
          <div className="empty">service unavailable：{errorText}</div>
        </section>
      ) : !summary ? (
        <section className="section card">
          <div className="empty">暂无数据</div>
        </section>
      ) : (
        <>
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
                <div className="metric-label">任务总数</div>
                <div className="metric-value">{summary.task_approval.task_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">待审批</div>
                <div className="metric-value">{summary.task_approval.pending_approval_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">最近审计事件</div>
                <div className="metric-value">{summary.audit.event_count}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pilot reports</div>
                <div className="metric-value">{summary.pilot_reports.total_reports}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">LLM 成本</div>
                <div className="metric-value">{summary.runtime_metrics.total_cost?.toFixed?.(4) ?? "-"}</div>
              </div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">deployment 检查摘要</h2>
            <div className="stack">
              <div className="mono">
                env={summary.deployment.environment || "-"} checks={summary.deployment.check_count} errors=
                {summary.deployment.error_count} warnings={summary.deployment.warning_count}
              </div>
              {summary.deployment.error_count > 0 ? (
                <div className="empty">error: {summary.deployment.errors.join(" | ")}</div>
              ) : null}
              {summary.deployment.warning_count > 0 ? (
                <div className="empty">warning: {summary.deployment.warnings.join(" | ")}</div>
              ) : null}
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">runtime metrics 摘要</h2>
            <div className="stack">
              <div className="mono">
                tasks={summary.runtime_metrics.task_count ?? 0} success={summary.runtime_metrics.success_count ?? 0} failed=
                {summary.runtime_metrics.failed_count ?? 0} waiting={summary.runtime_metrics.waiting_approval_count ?? 0}
              </div>
              <div className="mono">
                tokens={summary.runtime_metrics.total_prompt_tokens ?? 0}/
                {summary.runtime_metrics.total_completion_tokens ?? 0} cost={summary.runtime_metrics.total_cost ?? 0}
              </div>
              <div className="mono">
                llm_budget={compactJson(summary.runtime_metrics.llm_budget)} llm_cache=
                {compactJson(summary.runtime_metrics.llm_cache)}
              </div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">tasks / approvals（最近）</h2>
            <div className="stack">
              <div className="mono">
                task_status_counts={compactJson(summary.task_approval.task_status_counts)}
              </div>
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
                          <td className="mono">{item.task_id}</td>
                          <td>{item.status || "-"}</td>
                          <td>{item.mode || "-"}</td>
                          <td>{formatDateTime(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">audit 最近事件（脱敏）</h2>
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
                        <td className="mono">{event.event_id}</td>
                        <td>{event.event_type}</td>
                        <td>{event.outcome || "-"}</td>
                        <td className="mono">{event.request_id || "-"}</td>
                        <td>{event.summary || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">pilot reports / demo evidence（只读）</h2>
            <div className="stack">
              <div className="mono">
                directory_exists={String(summary.pilot_reports.directory_exists)} report_dir=
                {summary.pilot_reports.report_dir}
              </div>
              {summary.pilot_reports.reports.length === 0 ? (
                <div className="empty">no reports</div>
              ) : (
                <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
                  {summary.pilot_reports.reports.map((item) => (
                    <li key={item.report_id}>
                      <div className="mono">
                        {item.generated_at} | {item.scenario} | {item.outcome} | request_id=
                        {item.request_id || "<empty>"}
                      </div>
                      <div className="mono">
                        fallback={String(item.fallback_used)} cost={item.cost} tokens={item.total_tokens} audit_event_id=
                        {item.audit_event_id || "<empty>"}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <div className="empty">demo_e2e 提示：{summary.demo_evidence.tip}</div>
              <div className="toolbar">
                <Link className="button secondary" href="/llm">
                  查看 LLM Pilot
                </Link>
                <Link className="button secondary" href="/audit">
                  查看审计列表
                </Link>
                <Link className="button secondary" href="/metrics">
                  查看指标中心
                </Link>
              </div>
              <div className="mono">
                runbook={summary.demo_evidence.runbook_path} script={summary.demo_evidence.script_path}
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
