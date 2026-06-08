import Link from "next/link";
import { getOperationsSummary } from "@/lib/api/operations";
import { formatDateTime } from "@/lib/status";

function boolLabel(value: boolean): string {
  return value ? "Yes" : "No";
}

function optionalBoolLabel(value?: boolean): string {
  return typeof value === "boolean" ? boolLabel(value) : "-";
}

function compactList(value?: string[]): string {
  return value && value.length > 0 ? value.join(" | ") : "none";
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

function v4EvidenceEntryState(directoryExists: boolean, reportCount: number): string {
  if (!directoryExists) {
    return "directory_missing";
  }
  if (reportCount <= 0) {
    return "no_json_reports";
  }
  return "metadata_available";
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
                <div className="metric-label">v4 evidence reports</div>
                <div className="metric-value">{summary.observability.v4_evidence?.total_json_report_count ?? 0}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pilot bootstrap</div>
                <div className="metric-value">{summary.observability.production_pilot_bootstrap?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">frontend build</div>
                <div className="metric-value">{summary.observability.frontend_production_build?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">runtime smoke</div>
                <div className="metric-value">{summary.observability.production_runtime_smoke?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pilot signoff</div>
                <div className="metric-value">{summary.observability.production_pilot_signoff?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">business read</div>
                <div className="metric-value">{summary.observability.business_system_read_smoke?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">business readiness</div>
                <div className="metric-value">
                  {summary.observability.business_system_production_readiness?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">real env</div>
                <div className="metric-value">
                  {summary.observability.real_production_environment_checklist?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">landing inputs</div>
                <div className="metric-value">{summary.observability.production_landing_input_readiness?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">landing action pack</div>
                <div className="metric-value">{summary.observability.production_landing_action_pack?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">blocker resolution</div>
                <div className="metric-value">
                  {summary.observability.production_landing_blocker_resolution?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">final verification</div>
                <div className="metric-value">
                  {summary.observability.production_landing_final_verification?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pilot evidence</div>
                <div className="metric-value">{summary.observability.production_pilot_evidence_bundle?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">controlled pilot</div>
                <div className="metric-value">
                  {summary.observability.controlled_pilot_status_summary?.controlled_internal_pilot ??
                    summary.observability.controlled_pilot_launch_gate?.controlled_pilot ??
                    "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">local preflight</div>
                <div className="metric-value">
                  {summary.observability.controlled_pilot_console_preflight?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">local verify</div>
                <div className="metric-value">{summary.observability.controlled_pilot_console_verify?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">public launch</div>
                <div className="metric-value">
                  {summary.observability.controlled_pilot_status_summary?.public_production_direct_launch ?? "No-Go"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">public gaps</div>
                <div className="metric-value">
                  {summary.observability.controlled_pilot_status_summary?.public_production_gap_count ?? 0}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">signoff ack</div>
                <div className="metric-value">{summary.observability.manual_signoff_evidence_ack_status?.status ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">signoff closeout</div>
                <div className="metric-value">
                  {summary.observability.production_landing_signoff_closeout?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">pre-signoff gate</div>
                <div className="metric-value">
                  {summary.observability.production_landing_pre_signoff_gate?.status ?? "-"}
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">reviewer packet</div>
                <div className="metric-value">
                  {summary.observability.production_landing_signoff_reviewer_packet?.status ?? "-"}
                </div>
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
            <h2 className="card-title">Production pilot signoff (read only)</h2>
            {!summary.observability.production_pilot_signoff ? (
              <div className="empty">no signoff summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_pilot_signoff.status} recommendation=
                  {summary.observability.production_pilot_signoff.recommendation} production_pilot=
                  {summary.observability.production_pilot_signoff.production_pilot}
                </div>
                <div className="mono path-break">
                  enterprise_landing_state={summary.observability.production_pilot_signoff.enterprise_landing_state} manual_review_ready=
                  {String(summary.observability.production_pilot_signoff.controlled_pilot_manual_review_ready)}
                </div>
                <div className="mono path-break">
                  database_connected={String(summary.observability.production_pilot_signoff.database_connected)} redis_connected=
                  {String(summary.observability.production_pilot_signoff.redis_connected)} external_mcp_connected=
                  {String(summary.observability.production_pilot_signoff.external_mcp_connected)} real_infra_ready=
                  {String(summary.observability.production_pilot_signoff.real_infra_ready)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_pilot_signoff.latest_report_present)} report_dir=
                  {summary.observability.production_pilot_signoff.report_dir}
                </div>
                <div className="mono path-break">
                  readiness_items={summary.observability.production_pilot_signoff.readiness_item_count} manual_required=
                  {String(summary.observability.production_pilot_signoff.manual_signoff_required)} manual_completed=
                  {optionalBoolLabel(summary.observability.production_pilot_signoff.manual_signoff_completed)}
                </div>
                <div className="mono path-break">
                  manual_record_present=
                  {optionalBoolLabel(summary.observability.production_pilot_signoff.manual_signoff_record_present)} package_status=
                  {summary.observability.production_pilot_signoff.manual_signoff_package_status ?? "-"} decision=
                  {summary.observability.production_pilot_signoff.manual_signoff_decision ?? "-"}
                </div>
                <div className="mono path-break">
                  manual_roles={compactList(summary.observability.production_pilot_signoff.manual_signoff_roles)}
                </div>
                <div className="mono path-break">
                  manual_blockers={compactList(summary.observability.production_pilot_signoff.manual_signoff_blockers)}
                </div>
                <div className="mono path-break">
                  closure_items=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.closure_item_count} review_ready=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.review_ready_count} evidence_missing=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_missing_count} evidence_incomplete=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_incomplete_count} blocked=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.blocked_closure_count}
                </div>
                <div className="mono path-break">
                  evidence_ready_local=
                  {
                    summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_readiness_summary
                      .local_evidence_available_count
                  } runbook_only=
                  {
                    summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_readiness_summary
                      .runbook_only_count
                  } evidence_missing_ready=
                  {
                    summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_readiness_summary
                      .missing_count
                  } manual_review_required=
                  {String(
                    summary.observability.production_pilot_signoff.closure_evidence_summary.evidence_readiness_summary
                      .manual_review_required,
                  )}
                </div>
                <div className="mono path-break">
                  latest_closure_report=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.latest_report || "-"} closure_report_count=
                  {summary.observability.production_pilot_signoff.closure_evidence_summary.report_count}
                </div>
                <div className="mono path-break">
                  auto_signed={String(summary.observability.production_pilot_signoff.auto_signed)} auto_approved=
                  {String(summary.observability.production_pilot_signoff.auto_approved)} public_production_direct_launch=
                  {summary.observability.production_pilot_signoff.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.production_pilot_signoff.secret_plaintext_output)}
                </div>
                {summary.observability.production_pilot_signoff.production_blockers.length === 0 ? (
                  <div className="empty">no production blockers</div>
                ) : (
                  <div className="mono path-break">
                    production_blockers={summary.observability.production_pilot_signoff.production_blockers.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing input readiness (read only)</h2>
            {!summary.observability.production_landing_input_readiness ? (
              <div className="empty">no landing input readiness summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_input_readiness.status} ready_input_count=
                  {summary.observability.production_landing_input_readiness.ready_input_count} required_input_count=
                  {summary.observability.production_landing_input_readiness.required_input_count} missing_input_count=
                  {summary.observability.production_landing_input_readiness.missing_input_count} blocked_input_count=
                  {summary.observability.production_landing_input_readiness.blocked_input_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_input_readiness.latest_report_present)} report_dir=
                  {summary.observability.production_landing_input_readiness.report_dir}
                </div>
                <div className="mono path-break">
                  sources=
                  {Object.entries(summary.observability.production_landing_input_readiness.source_reports ?? {})
                    .map(([key, value]) => `${key}:${value}`)
                    .join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_input_readiness.public_production_direct_launch} auto_approved=
                  {String(summary.observability.production_landing_input_readiness.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_input_readiness.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_input_readiness.secret_plaintext_output)}
                </div>

                {summary.observability.production_landing_input_readiness.inputs.length === 0 ? (
                  <div className="empty">run python scripts/production_landing_input_readiness.py to generate first report</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>input_id</th>
                          <th>status</th>
                          <th>missing</th>
                          <th>ready</th>
                          <th>flags</th>
                          <th>first gaps</th>
                          <th>next action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_input_readiness.inputs.map((item) => (
                          <tr key={item.input_id}>
                            <td className="mono path-break">{item.input_id}</td>
                            <td>{item.status}</td>
                            <td>{item.missing_count}</td>
                            <td>
                              {item.closure_item_count > 0
                                ? `${item.ready_count}/${item.closure_item_count}`
                                : item.status === "ready"
                                  ? "yes"
                                  : "no"}
                            </td>
                            <td className="mono path-break">
                              present={String(item.present)} read_only={String(item.read_only)} write_enabled=
                              {String(item.write_enabled)} token_present={String(item.token_present)} database=
                              {String(item.database_connected)} redis={String(item.redis_connected)} mcp=
                              {String(item.external_mcp_connected)} real_infra_ready={String(item.real_infra_ready)}
                            </td>
                            <td className="mono path-break">{item.missing_conditions.slice(0, 4).join(" | ") || "-"}</td>
                            <td className="mono path-break">
                              {item.next_action || "-"}
                              {item.command_after_fill ? ` | ${item.command_after_fill}` : ""}
                              {item.required_env.length > 0 ? ` | env=${item.required_env.slice(0, 6).join(" ; ")}` : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Manual signoff evidence acknowledgement (read only)</h2>
            {!summary.observability.manual_signoff_evidence_ack_status ? (
              <div className="empty">no manual signoff evidence acknowledgement summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.manual_signoff_evidence_ack_status.status} recommended_accept_count=
                  {summary.observability.manual_signoff_evidence_ack_status.recommended_accept_count}/
                  {summary.observability.manual_signoff_evidence_ack_status.item_count} blocked_item_count=
                  {summary.observability.manual_signoff_evidence_ack_status.blocked_item_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.manual_signoff_evidence_ack_status.latest_report_present)} report_dir=
                  {summary.observability.manual_signoff_evidence_ack_status.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.manual_signoff_evidence_ack_status.public_production_direct_launch} auto_approved=
                  {String(summary.observability.manual_signoff_evidence_ack_status.auto_approved)} auto_closed=
                  {String(summary.observability.manual_signoff_evidence_ack_status.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.manual_signoff_evidence_ack_status.secret_plaintext_output)}
                </div>

                {summary.observability.manual_signoff_evidence_ack_status.items.length === 0 ? (
                  <div className="empty">run python scripts/manual_signoff_evidence_ack_status.py to generate first report</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>item</th>
                          <th>source</th>
                          <th>recommended</th>
                          <th>missing</th>
                          <th>latest report</th>
                          <th>first gaps</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.manual_signoff_evidence_ack_status.items.map((item) => (
                          <tr key={item.item}>
                            <td className="mono path-break">{item.item}</td>
                            <td>{item.source_status}</td>
                            <td>{String(item.recommended_accept)}</td>
                            <td>{item.missing_count}</td>
                            <td className="mono path-break">{item.latest_report || "-"}</td>
                            <td className="mono path-break">{item.missing_conditions.slice(0, 4).join(" | ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Manual signoff record validation (read only)</h2>
            {!summary.observability.manual_signoff_record_validation ? (
              <div className="empty">no manual signoff record validation summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.manual_signoff_record_validation.status} decision=
                  {summary.observability.manual_signoff_record_validation.decision} ack_status=
                  {summary.observability.manual_signoff_record_validation.ack_status} missing_conditions=
                  {summary.observability.manual_signoff_record_validation.missing_condition_count}
                </div>
                <div className="mono path-break">
                  record_present={String(summary.observability.manual_signoff_record_validation.signoff_record_present)} completed=
                  {String(summary.observability.manual_signoff_record_validation.manual_signoff_completed)} report_present=
                  {String(summary.observability.manual_signoff_record_validation.latest_report_present)} report_dir=
                  {summary.observability.manual_signoff_record_validation.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.manual_signoff_record_validation.public_production_direct_launch} auto_approved=
                  {String(summary.observability.manual_signoff_record_validation.auto_approved)} auto_closed=
                  {String(summary.observability.manual_signoff_record_validation.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.manual_signoff_record_validation.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  roles=
                  {summary.observability.manual_signoff_record_validation.roles
                    .map((item) => `${item.role}:name=${String(item.name_present)},approved=${String(item.approved)}`)
                    .join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  evidence_acknowledgements=
                  {summary.observability.manual_signoff_record_validation.evidence_acknowledgements
                    .map((item) => `${item.item}:accepted=${String(item.accepted)},note=${String(item.note_present)}`)
                    .join(" | ") || "-"}
                </div>
                {summary.observability.manual_signoff_record_validation.missing_conditions.length === 0 ? (
                  <div className="empty">no manual signoff validation gaps</div>
                ) : (
                  <div className="mono path-break">
                    first_missing_conditions=
                    {summary.observability.manual_signoff_record_validation.missing_conditions.slice(0, 12).join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Manual signoff record fill (explicit)</h2>
            {!summary.observability.manual_signoff_record_fill ? (
              <div className="empty">no manual signoff record fill summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.manual_signoff_record_fill.status} filled=
                  {String(summary.observability.manual_signoff_record_fill.filled)} completed=
                  {String(summary.observability.manual_signoff_record_fill.manual_signoff_completed)} decision=
                  {summary.observability.manual_signoff_record_fill.decision} missing_conditions=
                  {summary.observability.manual_signoff_record_fill.missing_condition_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.manual_signoff_record_fill.latest_report_present)} report_dir=
                  {summary.observability.manual_signoff_record_fill.report_dir}
                </div>
                <div className="mono path-break">
                  signoff_record={summary.observability.manual_signoff_record_fill.signoff_record || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.manual_signoff_record_fill.public_production_direct_launch} auto_signed=
                  {String(summary.observability.manual_signoff_record_fill.auto_signed)} auto_approved=
                  {String(summary.observability.manual_signoff_record_fill.auto_approved)} auto_closed=
                  {String(summary.observability.manual_signoff_record_fill.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.manual_signoff_record_fill.secret_plaintext_output)}
                </div>
                {summary.observability.manual_signoff_record_fill.missing_conditions.length === 0 ? (
                  <div className="empty">no fill gaps</div>
                ) : (
                  <div className="mono path-break">
                    first_missing_conditions=
                    {summary.observability.manual_signoff_record_fill.missing_conditions.slice(0, 12).join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing pre-signoff gate (read only)</h2>
            {!summary.observability.production_landing_pre_signoff_gate ? (
              <div className="empty">no production landing pre-signoff gate summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_pre_signoff_gate.status} ready_for_manual_signoff=
                  {String(summary.observability.production_landing_pre_signoff_gate.ready_for_manual_signoff)} technical_evidence_ready=
                  {String(summary.observability.production_landing_pre_signoff_gate.technical_evidence_ready)} non_signoff_blockers=
                  {summary.observability.production_landing_pre_signoff_gate.non_signoff_blocker_count}
                </div>
                <div className="mono path-break">
                  ack_ready={String(summary.observability.production_landing_pre_signoff_gate.ack_ready)} action_required_input_count=
                  {summary.observability.production_landing_pre_signoff_gate.action_required_input_count} report_present=
                  {String(summary.observability.production_landing_pre_signoff_gate.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.production_landing_pre_signoff_gate.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_pre_signoff_gate.public_production_direct_launch} auto_signed=
                  {String(summary.observability.production_landing_pre_signoff_gate.auto_signed)} auto_approved=
                  {String(summary.observability.production_landing_pre_signoff_gate.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_pre_signoff_gate.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_pre_signoff_gate.secret_plaintext_output)}
                </div>
                {summary.observability.production_landing_pre_signoff_gate.non_signoff_blockers.length === 0 ? (
                  <div className="empty">no non-signoff blockers</div>
                ) : (
                  <div className="mono path-break">
                    non_signoff_blockers=
                    {summary.observability.production_landing_pre_signoff_gate.non_signoff_blockers.slice(0, 12).join(" | ")}
                  </div>
                )}
                <div className="mono path-break">
                  signoff_only_missing=
                  {summary.observability.production_landing_pre_signoff_gate.signoff_only_missing_conditions
                    .slice(0, 12)
                    .join(" | ") || "none"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing signoff reviewer packet (read only)</h2>
            {!summary.observability.production_landing_signoff_reviewer_packet ? (
              <div className="empty">no production landing signoff reviewer packet summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_signoff_reviewer_packet.status} ready_for_manual_signoff=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.ready_for_manual_signoff)} technical_evidence_ready=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.technical_evidence_ready)} non_signoff_blockers=
                  {summary.observability.production_landing_signoff_reviewer_packet.non_signoff_blocker_count}
                </div>
                <div className="mono path-break">
                  ack_ready={String(summary.observability.production_landing_signoff_reviewer_packet.ack_ready)} missing_conditions=
                  {summary.observability.production_landing_signoff_reviewer_packet.missing_condition_count} report_present=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.production_landing_signoff_reviewer_packet.report_dir}
                </div>
                <div className="mono path-break">
                  closeout_command=
                  {summary.observability.production_landing_signoff_reviewer_packet.recommended_closeout_command || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_signoff_reviewer_packet.public_production_direct_launch} auto_signed=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.auto_signed)} auto_approved=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_signoff_reviewer_packet.secret_plaintext_output)}
                </div>
                {summary.observability.production_landing_signoff_reviewer_packet.evidence.length === 0 ? (
                  <div className="empty">no reviewer evidence listed</div>
                ) : (
                  <div className="mono path-break">
                    evidence=
                    {summary.observability.production_landing_signoff_reviewer_packet.evidence
                      .map((item) => `${item.source_id}:${item.status}`)
                      .join(" | ")}
                  </div>
                )}
                {summary.observability.production_landing_signoff_reviewer_packet.missing_conditions.length === 0 ? (
                  <div className="empty">no reviewer packet gaps</div>
                ) : (
                  <div className="mono path-break">
                    first_missing_conditions=
                    {summary.observability.production_landing_signoff_reviewer_packet.missing_conditions
                      .slice(0, 12)
                      .join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing signoff closeout (explicit)</h2>
            {!summary.observability.production_landing_signoff_closeout ? (
              <div className="empty">no production landing signoff closeout summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_signoff_closeout.status} final_status=
                  {summary.observability.production_landing_signoff_closeout.final_status || "-"} target_written=
                  {String(summary.observability.production_landing_signoff_closeout.target_record_written)} missing_conditions=
                  {summary.observability.production_landing_signoff_closeout.missing_condition_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_signoff_closeout.latest_report_present)} report_dir=
                  {summary.observability.production_landing_signoff_closeout.report_dir}
                </div>
                <div className="mono path-break">
                  signoff_record={summary.observability.production_landing_signoff_closeout.signoff_record || "-"}
                </div>
                <div className="mono path-break">
                  target_record={summary.observability.production_landing_signoff_closeout.target_record || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_signoff_closeout.public_production_direct_launch} auto_signed=
                  {String(summary.observability.production_landing_signoff_closeout.auto_signed)} auto_approved=
                  {String(summary.observability.production_landing_signoff_closeout.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_signoff_closeout.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_signoff_closeout.secret_plaintext_output)}
                </div>
                {summary.observability.production_landing_signoff_closeout.steps.length === 0 ? (
                  <div className="empty">no closeout steps executed</div>
                ) : (
                  <div className="mono path-break">
                    steps=
                    {summary.observability.production_landing_signoff_closeout.steps
                      .map((item) => `${item.step_id}:${item.status}`)
                      .join(" | ")}
                  </div>
                )}
                {summary.observability.production_landing_signoff_closeout.missing_conditions.length === 0 ? (
                  <div className="empty">no closeout gaps</div>
                ) : (
                  <div className="mono path-break">
                    first_missing_conditions=
                    {summary.observability.production_landing_signoff_closeout.missing_conditions.slice(0, 12).join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Manual signoff record promote (read only)</h2>
            {!summary.observability.manual_signoff_record_promote ? (
              <div className="empty">no manual signoff record promote summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.manual_signoff_record_promote.status} promoted=
                  {String(summary.observability.manual_signoff_record_promote.promoted)} target_written=
                  {String(summary.observability.manual_signoff_record_promote.target_record_written)} missing_conditions=
                  {summary.observability.manual_signoff_record_promote.missing_condition_count}
                </div>
                <div className="mono path-break">
                  source_present={String(summary.observability.manual_signoff_record_promote.source_record_present)} completed=
                  {String(summary.observability.manual_signoff_record_promote.manual_signoff_completed)} decision=
                  {summary.observability.manual_signoff_record_promote.decision} report_present=
                  {String(summary.observability.manual_signoff_record_promote.latest_report_present)}
                </div>
                <div className="mono path-break">
                  source_record={summary.observability.manual_signoff_record_promote.source_record || "-"}
                </div>
                <div className="mono path-break">
                  target_record={summary.observability.manual_signoff_record_promote.target_record || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.manual_signoff_record_promote.public_production_direct_launch} auto_approved=
                  {String(summary.observability.manual_signoff_record_promote.auto_approved)} auto_closed=
                  {String(summary.observability.manual_signoff_record_promote.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.manual_signoff_record_promote.secret_plaintext_output)}
                </div>
                {summary.observability.manual_signoff_record_promote.missing_conditions.length === 0 ? (
                  <div className="empty">no promote gaps</div>
                ) : (
                  <div className="mono path-break">
                    first_missing_conditions=
                    {summary.observability.manual_signoff_record_promote.missing_conditions.slice(0, 12).join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing action pack (read only)</h2>
            {!summary.observability.production_landing_action_pack ? (
              <div className="empty">no landing action pack summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_action_pack.status} required_input_count=
                  {summary.observability.production_landing_action_pack.required_input_count} report_present=
                  {String(summary.observability.production_landing_action_pack.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.production_landing_action_pack.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_action_pack.public_production_direct_launch} auto_approved=
                  {String(summary.observability.production_landing_action_pack.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_action_pack.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_action_pack.secret_plaintext_output)}
                </div>

                {summary.observability.production_landing_action_pack.required_inputs.length === 0 ? (
                  <div className="empty">no required inputs listed</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>input_id</th>
                          <th>status</th>
                          <th>template</th>
                          <th>draft</th>
                          <th>blocking_evidence</th>
                          <th>required_domains</th>
                          <th>required_env</th>
                          <th>command_after_fill</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_action_pack.required_inputs.map((item) => (
                          <tr key={item.input_id}>
                            <td className="mono path-break">{item.input_id}</td>
                            <td>{item.status || "-"}</td>
                            <td className="mono path-break">{item.template || "-"}</td>
                            <td className="mono path-break">{item.filled_record || item.draft || "-"}</td>
                            <td className="mono path-break">
                              {item.blocking_evidence_items && item.blocking_evidence_items.length > 0
                                ? item.blocking_evidence_items
                                    .map(
                                      (blocker) =>
                                        `${blocker.item}:${blocker.source_status}:${compactList(
                                          blocker.missing_conditions
                                        )}:acceptance=${compactList(blocker.acceptance_blockers ?? [])}:next=${
                                          blocker.safe_next_action || "-"
                                        }:${compactList(blocker.safe_commands)}`
                                    )
                                    .join(" | ")
                                : "-"}
                            </td>
                            <td className="mono path-break">{item.required_domains || "-"}</td>
                            <td className="mono path-break">{item.required_env || "-"}</td>
                            <td className="mono path-break">
                              {item.command_after_fill || "-"}
                              {item.promote_command_after_manual_fill
                                ? ` | ${item.promote_command_after_manual_fill}`
                                : ""}
                              {item.process_env_only_llm_preflight_command
                                ? ` | ${item.process_env_only_llm_preflight_command}`
                                : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="mono path-break">
                  templates={compactJson(summary.observability.production_landing_action_pack.template_status)}
                </div>
                {summary.observability.production_landing_action_pack.recommended_commands.length === 0 ? (
                  <div className="empty">no recommended commands</div>
                ) : (
                  <div className="mono path-break">
                    recommended_commands=
                    {summary.observability.production_landing_action_pack.recommended_commands.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing blocker resolution (read only)</h2>
            {!summary.observability.production_landing_blocker_resolution ? (
              <div className="empty">no blocker resolution summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_blocker_resolution.status} required_action_count=
                  {summary.observability.production_landing_blocker_resolution.required_action_count} report_present=
                  {String(summary.observability.production_landing_blocker_resolution.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.production_landing_blocker_resolution.report_dir}
                </div>
                <div className="mono path-break">
                  required_actions=
                  {summary.observability.production_landing_blocker_resolution.required_actions.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  source_blocked_or_failed=
                  {summary.observability.production_landing_blocker_resolution.source_blocked_or_failed.join(" | ") ||
                    "-"}{" "}
                  source_missing_conditions=
                  {summary.observability.production_landing_blocker_resolution.source_missing_conditions.join(" | ") ||
                    "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_blocker_resolution.public_production_direct_launch}{" "}
                  auto_approved={String(summary.observability.production_landing_blocker_resolution.auto_approved)}{" "}
                  auto_closed={String(summary.observability.production_landing_blocker_resolution.auto_closed)}{" "}
                  secret_plaintext_output=
                  {String(summary.observability.production_landing_blocker_resolution.secret_plaintext_output)}
                </div>

                {summary.observability.production_landing_blocker_resolution.actions.length === 0 ? (
                  <div className="empty">no blocker resolution actions listed</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>action_id</th>
                          <th>status</th>
                          <th>owner</th>
                          <th>evidence</th>
                          <th>safe_commands</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_blocker_resolution.actions.map((item) => (
                          <tr key={item.action_id}>
                            <td className="mono path-break">{item.action_id}</td>
                            <td>{item.status || "-"}</td>
                            <td>{item.owner || "-"}</td>
                            <td className="mono path-break">{compactJson(item.evidence)}</td>
                            <td className="mono path-break">{item.safe_commands.join(" | ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing final verification (read only)</h2>
            {!summary.observability.production_landing_final_verification ? (
              <div className="empty">no final verification summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_final_verification.status} passed_count=
                  {summary.observability.production_landing_final_verification.passed_count}/
                  {summary.observability.production_landing_final_verification.requirement_count} report_present=
                  {String(summary.observability.production_landing_final_verification.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.production_landing_final_verification.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_final_verification.public_production_direct_launch}{" "}
                  auto_approved={String(summary.observability.production_landing_final_verification.auto_approved)}{" "}
                  auto_closed={String(summary.observability.production_landing_final_verification.auto_closed)}{" "}
                  secret_plaintext_output=
                  {String(summary.observability.production_landing_final_verification.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.production_landing_final_verification.missing_conditions.join(" | ") || "-"}
                </div>

                {summary.observability.production_landing_final_verification.requirements.length === 0 ? (
                  <div className="empty">no final verification requirements listed</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>requirement_id</th>
                          <th>passed</th>
                          <th>missing_conditions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_final_verification.requirements.map((item) => (
                          <tr key={item.requirement_id}>
                            <td className="mono path-break">{item.requirement_id}</td>
                            <td>{String(item.passed)}</td>
                            <td className="mono path-break">{item.missing_conditions.join(" | ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production pilot evidence bundle (read only)</h2>
            {!summary.observability.production_pilot_evidence_bundle ? (
              <div className="empty">no production pilot evidence bundle summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_pilot_evidence_bundle.status} controlled_pilot=
                  {summary.observability.production_pilot_evidence_bundle.controlled_pilot} controlled_pilot_ready=
                  {String(summary.observability.production_pilot_evidence_bundle.controlled_pilot_ready)}
                </div>
                <div className="mono path-break">
                  final_verification=
                  {summary.observability.production_pilot_evidence_bundle.final_verification_passed_count}/
                  {summary.observability.production_pilot_evidence_bundle.final_verification_requirement_count} missing_conditions=
                  {summary.observability.production_pilot_evidence_bundle.missing_condition_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_pilot_evidence_bundle.latest_report_present)} report_dir=
                  {summary.observability.production_pilot_evidence_bundle.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_pilot_evidence_bundle.public_production_direct_launch} auto_approved=
                  {String(summary.observability.production_pilot_evidence_bundle.auto_approved)} auto_closed=
                  {String(summary.observability.production_pilot_evidence_bundle.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_pilot_evidence_bundle.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.production_pilot_evidence_bundle.missing_conditions.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  next_actions={summary.observability.production_pilot_evidence_bundle.next_actions.join(" | ") || "-"}
                </div>

                {Object.keys(summary.observability.production_pilot_evidence_bundle.sources).length === 0 ? (
                  <div className="empty">no source summaries</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>source</th>
                          <th>status</th>
                          <th>present</th>
                          <th>counts</th>
                          <th>secret</th>
                          <th>missing</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.observability.production_pilot_evidence_bundle.sources).map(
                          ([sourceId, item]) => (
                            <tr key={sourceId}>
                              <td className="mono path-break">{sourceId}</td>
                              <td>{item.status}</td>
                              <td>{String(item.present)}</td>
                              <td className="mono path-break">
                                passed={item.passed_count}/{item.requirement_count} missing=
                                {item.missing_condition_count} gaps={item.open_gap_count}/{item.gap_count} domains=
                                {item.domain_count}
                              </td>
                              <td className="mono path-break">
                                secret_detected={String(item.secret_detected)} secret_plaintext_output=
                                {String(item.secret_plaintext_output)}
                              </td>
                              <td className="mono path-break">{item.missing_conditions.join(" | ") || "-"}</td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">受控试点总状态摘要（只读）</h2>
            {!summary.observability.controlled_pilot_status_summary ? (
              <div className="empty">暂无受控试点总状态摘要</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_status_summary.status} controlled_internal_pilot=
                  {summary.observability.controlled_pilot_status_summary.controlled_internal_pilot}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_status_summary.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_status_summary.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_status_summary.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_status_summary.report_dir}
                </div>
                <div className="mono path-break">
                  latest_report={summary.observability.controlled_pilot_status_summary.latest_json_path || "-"}
                </div>
                <div className="mono path-break">
                  operations_console_smoke_execute=
                  {String(summary.observability.controlled_pilot_status_summary.operations_console_smoke_execute)} runtime_smoke_passed=
                  {String(summary.observability.controlled_pilot_status_summary.runtime_smoke_passed)}
                </div>
                <div className="mono path-break">
                  blocking_reports=
                  {summary.observability.controlled_pilot_status_summary.blocking_reports.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  public_production_gap_count=
                  {summary.observability.controlled_pilot_status_summary.public_production_gap_count} public_production_gaps=
                  {compactList(summary.observability.controlled_pilot_status_summary.public_production_gaps)}
                </div>
                {Object.keys(summary.observability.controlled_pilot_status_summary.source_statuses).length === 0 ? (
                  <div className="empty">暂无来源状态</div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>来源</th>
                          <th>status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.observability.controlled_pilot_status_summary.source_statuses).map(
                          ([sourceId, status]) => (
                            <tr key={sourceId}>
                              <td className="mono path-break">{sourceId}</td>
                              <td>{status}</td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">受控试点操作员交接包（只读）</h2>
            {!summary.observability.controlled_pilot_operator_packet ? (
              <div className="empty">暂无受控试点操作员交接包</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_operator_packet.status} controlled_internal_pilot=
                  {summary.observability.controlled_pilot_operator_packet.controlled_internal_pilot} window_id=
                  {summary.observability.controlled_pilot_operator_packet.window_id || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_operator_packet.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_operator_packet.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_operator_packet.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_operator_packet.report_dir}
                </div>
                <div className="mono path-break">
                  latest_report={summary.observability.controlled_pilot_operator_packet.latest_json_path || "-"}
                </div>
                <div className="mono path-break">
                  operator_commands={summary.observability.controlled_pilot_operator_packet.operator_command_count} pilot_roles=
                  {summary.observability.controlled_pilot_operator_packet.pilot_role_count} missing_conditions=
                  {summary.observability.controlled_pilot_operator_packet.missing_condition_count}
                </div>
                <div className="mono path-break">
                  rollback_required={String(summary.observability.controlled_pilot_operator_packet.rollback_required)} external_expansion_requires_new_manual_go_no_go=
                  {String(
                    summary.observability.controlled_pilot_operator_packet
                      .external_expansion_requires_new_manual_go_no_go,
                  )}
                </div>
                <div className="mono path-break">
                  business_data_written={String(summary.observability.controlled_pilot_operator_packet.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_operator_packet.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_operator_packet.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  public_production_gap_count=
                  {summary.observability.controlled_pilot_operator_packet.public_production_gap_count} public_production_gaps=
                  {compactList(summary.observability.controlled_pilot_operator_packet.public_production_gaps)}
                </div>
                <div className="mono path-break">
                  business_read_status=
                  {summary.observability.controlled_pilot_operator_packet.business_system_read_smoke.status || "-"} auth_mode=
                  {summary.observability.controlled_pilot_operator_packet.business_system_read_smoke.auth_mode || "-"} business_read_executed=
                  {String(
                    summary.observability.controlled_pilot_operator_packet.business_system_read_smoke
                      .business_read_executed,
                  )}
                </div>
                {Object.keys(summary.observability.controlled_pilot_operator_packet.evidence_paths).length === 0 ? (
                  <div className="empty">暂无操作员交接包证据路径</div>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>证据</th>
                          <th>路径</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.observability.controlled_pilot_operator_packet.evidence_paths).map(
                          ([sourceId, path]) => (
                            <tr key={sourceId}>
                              <td className="mono path-break">{sourceId}</td>
                              <td className="mono path-break">{path}</td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_operator_packet.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot delivery gate (read only)</h2>
            {!summary.observability.controlled_pilot_delivery_gate ? (
              <div className="empty">no controlled pilot delivery gate summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_delivery_gate.status} ready=
                  {String(summary.observability.controlled_pilot_delivery_gate.controlled_pilot_delivery_ready)} scope=
                  {summary.observability.controlled_pilot_delivery_gate.enterprise_landing_scope || "-"}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_delivery_gate.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_delivery_gate.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_delivery_gate.public_production_direct_launch} missing_conditions=
                  {summary.observability.controlled_pilot_delivery_gate.missing_condition_count}
                </div>
                <div className="mono path-break">
                  accepted_remaining_gaps=
                  {summary.observability.controlled_pilot_delivery_gate.accepted_remaining_gaps.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  auto_approved={String(summary.observability.controlled_pilot_delivery_gate.auto_approved)} auto_closed=
                  {String(summary.observability.controlled_pilot_delivery_gate.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_delivery_gate.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_delivery_gate.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot run packet (read only)</h2>
            {!summary.observability.controlled_pilot_run_packet ? (
              <div className="empty">no controlled pilot run packet summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_run_packet.status} ready=
                  {String(summary.observability.controlled_pilot_run_packet.run_packet_ready)} internal_pilot=
                  {summary.observability.controlled_pilot_run_packet.controlled_internal_pilot}
                </div>
                <div className="mono path-break">
                  scope={summary.observability.controlled_pilot_run_packet.ready_scope || "-"} public_production_direct_launch=
                  {summary.observability.controlled_pilot_run_packet.public_production_direct_launch} missing_conditions=
                  {summary.observability.controlled_pilot_run_packet.missing_condition_count}
                </div>
                <div className="mono path-break">
                  accepted_remaining_gaps=
                  {summary.observability.controlled_pilot_run_packet.accepted_remaining_gaps.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  real_production_remaining_gaps=
                  {summary.observability.controlled_pilot_run_packet.real_production_remaining_gaps.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  business_boundary={compactJson(summary.observability.controlled_pilot_run_packet.business_system_boundary)}
                </div>
                <div className="mono path-break">
                  safety_boundary={compactJson(summary.observability.controlled_pilot_run_packet.safety_boundary)}
                </div>
                <div className="mono path-break">
                  commands={compactJson(summary.observability.controlled_pilot_run_packet.operator_commands)}
                </div>
                <div className="mono path-break">
                  source_statuses={compactJson(summary.observability.controlled_pilot_run_packet.source_statuses)}
                </div>
                <div className="mono path-break">
                  secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_run_packet.secret_plaintext_output)} business_data_written=
                  {String(summary.observability.controlled_pilot_run_packet.business_data_written)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_run_packet.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Evidence archive manifest (read only)</h2>
            {!summary.observability.evidence_archive ? (
              <div className="empty">no evidence archive summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.evidence_archive.status} manifest_id=
                  {summary.observability.evidence_archive.manifest_id || "-"} reports=
                  {summary.observability.last_known_report_counts.evidence_archive_reports ?? 0}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.evidence_archive.latest_report_present)} report_dir=
                  {summary.observability.evidence_archive.report_dir}
                </div>
                <div className="mono path-break">
                  total_files={summary.observability.evidence_archive.total_files} total_size_bytes=
                  {summary.observability.evidence_archive.total_size_bytes} read_only=
                  {String(summary.observability.evidence_archive.read_only)} real_llm_executed=
                  {String(summary.observability.evidence_archive.real_llm_executed)}
                </div>
                <div className="mono path-break">
                  retention_policy={compactJson(summary.observability.evidence_archive.retention_policy)}
                </div>
                <div className="mono path-break">
                  missing_expected_types=
                  {summary.observability.evidence_archive.missing_expected_types.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  latest_by_type={compactJson(summary.observability.evidence_archive.latest_by_type)}
                </div>
                <div className="mono path-break">
                  boundary_declarations=
                  {summary.observability.evidence_archive.boundary_declarations.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot launch gate (read only)</h2>
            {!summary.observability.controlled_pilot_launch_gate ? (
              <div className="empty">no controlled pilot launch gate summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_launch_gate.status} controlled_pilot=
                  {summary.observability.controlled_pilot_launch_gate.controlled_pilot} ready=
                  {String(summary.observability.controlled_pilot_launch_gate.ready_for_controlled_pilot)}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_launch_gate.public_production_direct_launch} manual_signoff_required=
                  {String(summary.observability.controlled_pilot_launch_gate.manual_signoff_required)}
                </div>
                <div className="mono path-break">
                  delivery_gate={summary.observability.controlled_pilot_launch_gate.delivery_gate_status || "-"} accepted_remaining_gaps=
                  {(summary.observability.controlled_pilot_launch_gate.accepted_remaining_gaps || []).join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  evidence_bundle={summary.observability.controlled_pilot_launch_gate.evidence_bundle_status} final_verification=
                  {summary.observability.controlled_pilot_launch_gate.final_verification_status} signoff_closeout=
                  {summary.observability.controlled_pilot_launch_gate.signoff_closeout_status} bootstrap=
                  {summary.observability.controlled_pilot_launch_gate.bootstrap_status}
                </div>
                <div className="mono path-break">
                  final_verification=
                  {summary.observability.controlled_pilot_launch_gate.final_verification_passed_count}/
                  {summary.observability.controlled_pilot_launch_gate.final_verification_requirement_count} missing_conditions=
                  {summary.observability.controlled_pilot_launch_gate.missing_condition_count}
                </div>
                <div className="mono path-break">
                  safe_next_action={summary.observability.controlled_pilot_launch_gate.safe_next_action}
                </div>
                <div className="mono path-break">
                  operator_command={summary.observability.controlled_pilot_launch_gate.operator_command}
                </div>
                <div className="mono path-break">
                  auto_approved={String(summary.observability.controlled_pilot_launch_gate.auto_approved)} auto_closed=
                  {String(summary.observability.controlled_pilot_launch_gate.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_launch_gate.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_launch_gate.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot launch package (read only)</h2>
            {!summary.observability.controlled_pilot_launch_package ? (
              <div className="empty">no controlled pilot launch package summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_launch_package.status} controlled_pilot=
                  {summary.observability.controlled_pilot_launch_package.controlled_pilot} ready=
                  {String(summary.observability.controlled_pilot_launch_package.launch_package_ready)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_launch_package.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_launch_package.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_launch_package.public_production_direct_launch} manual_signoff_required=
                  {String(summary.observability.controlled_pilot_launch_package.manual_signoff_required)}
                </div>
                <div className="mono path-break">
                  accepted_remaining_gaps=
                  {(summary.observability.controlled_pilot_launch_package.accepted_remaining_gaps || []).join(" | ") ||
                    "-"}
                </div>
                <div className="mono path-break">
                  safe_next_action={summary.observability.controlled_pilot_launch_package.safe_next_action} missing_conditions=
                  {summary.observability.controlled_pilot_launch_package.missing_condition_count}
                </div>
                <div className="mono path-break">
                  launch_scope={summary.observability.controlled_pilot_launch_package.launch_window.scope || "-"} rollback_required=
                  {String(summary.observability.controlled_pilot_launch_package.launch_window.rollback_required ?? false)} external_expansion_requires_new_manual_go_no_go=
                  {String(
                    summary.observability.controlled_pilot_launch_package.launch_window
                      .external_expansion_requires_new_manual_go_no_go ?? false,
                  )}
                </div>
                <div className="mono path-break">
                  business_data_written={String(summary.observability.controlled_pilot_launch_package.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_launch_package.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_launch_package.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  auto_approved={String(summary.observability.controlled_pilot_launch_package.auto_approved)} auto_closed=
                  {String(summary.observability.controlled_pilot_launch_package.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_launch_package.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_launch_package.missing_conditions.join(" | ") || "-"}
                </div>

                {summary.observability.controlled_pilot_launch_package.operator_commands.length === 0 ? (
                  <div className="empty">no operator commands</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>operator_command</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.controlled_pilot_launch_package.operator_commands.map((command) => (
                          <tr key={command}>
                            <td className="mono path-break">{command}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {summary.observability.controlled_pilot_launch_package.pilot_roles.length === 0 ? (
                  <div className="empty">no pilot roles</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>role</th>
                          <th>responsibility</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.controlled_pilot_launch_package.pilot_roles.map((item) => (
                          <tr key={item.role}>
                            <td className="mono">{item.role}</td>
                            <td>{item.responsibility}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {Object.keys(summary.observability.controlled_pilot_launch_package.sources).length === 0 ? (
                  <div className="empty">no launch package sources</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>source</th>
                          <th>status</th>
                          <th>present</th>
                          <th>secret</th>
                          <th>missing</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(summary.observability.controlled_pilot_launch_package.sources).map(
                          ([sourceId, item]) => (
                            <tr key={sourceId}>
                              <td className="mono path-break">{sourceId}</td>
                              <td>{item.status}</td>
                              <td>{String(item.present)}</td>
                              <td>{String(item.secret_detected)}</td>
                              <td className="mono path-break">{item.missing_conditions.join(" | ") || "-"}</td>
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">受控试点一键验证报告（只读）</h2>
            {!summary.observability.controlled_pilot_console_verify ? (
              <div className="empty">暂无受控试点一键验证报告</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_console_verify.status} controlled_internal_pilot=
                  {summary.observability.controlled_pilot_console_verify.controlled_internal_pilot} missing_conditions=
                  {summary.observability.controlled_pilot_console_verify.missing_condition_count}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_console_verify.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_console_verify.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  frontend={summary.observability.controlled_pilot_console_verify.frontend_url || "-"} backend=
                  {summary.observability.controlled_pilot_console_verify.backend_url || "-"}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_console_verify.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_console_verify.report_dir}
                </div>
                <div className="mono path-break">
                  latest_report={summary.observability.controlled_pilot_console_verify.latest_json_path || "-"}
                </div>
                <div className="mono path-break">
                  pid_file_present_after_verify=
                  {String(summary.observability.controlled_pilot_console_verify.pid_file_present_after_verify)} real_llm_executed=
                  {String(summary.observability.controlled_pilot_console_verify.real_llm_executed)}
                </div>
                <div className="mono path-break">
                  business_data_written={String(summary.observability.controlled_pilot_console_verify.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_console_verify.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_console_verify.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_console_verify.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">受控试点本地预检报告（只读）</h2>
            {!summary.observability.controlled_pilot_console_preflight ? (
              <div className="empty">暂无受控试点本地预检报告</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_console_preflight.status} ready_for_local_verify=
                  {String(summary.observability.controlled_pilot_console_preflight.ready_for_local_verify)} blocking_conditions=
                  {summary.observability.controlled_pilot_console_preflight.blocking_condition_count}
                </div>
                <div className="mono path-break">
                  latest_verify={summary.observability.controlled_pilot_console_preflight.latest_verify_status} latest_verify_pilot=
                  {summary.observability.controlled_pilot_console_preflight.latest_verify_controlled_internal_pilot}
                </div>
                <div className="mono path-break">
                  recommended_command={summary.observability.controlled_pilot_console_preflight.recommended_command || "-"}
                </div>
                <div className="mono path-break">
                  frontend={summary.observability.controlled_pilot_console_preflight.frontend_url || "-"} backend=
                  {summary.observability.controlled_pilot_console_preflight.backend_url || "-"}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_console_preflight.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_console_preflight.report_dir}
                </div>
                <div className="mono path-break">
                  latest_report={summary.observability.controlled_pilot_console_preflight.latest_json_path || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_console_preflight.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_console_preflight.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  real_llm_executed={String(summary.observability.controlled_pilot_console_preflight.real_llm_executed)} business_data_written=
                  {String(summary.observability.controlled_pilot_console_preflight.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_console_preflight.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_console_preflight.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  blocking_conditions=
                  {summary.observability.controlled_pilot_console_preflight.blocking_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot window record (read only)</h2>
            {!summary.observability.controlled_pilot_window_record ? (
              <div className="empty">no controlled pilot window record summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_window_record.status} opened=
                  {String(summary.observability.controlled_pilot_window_record.opened)} window_id=
                  {summary.observability.controlled_pilot_window_record.window_id || "-"}
                </div>
                <div className="mono path-break">
                  opened_by={summary.observability.controlled_pilot_window_record.opened_by || "-"} confirm_open=
                  {summary.observability.controlled_pilot_window_record.confirm_open} controlled_pilot=
                  {summary.observability.controlled_pilot_window_record.controlled_pilot}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_window_record.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_window_record.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_window_record.public_production_direct_launch} manual_signoff_required=
                  {String(summary.observability.controlled_pilot_window_record.manual_signoff_required)}
                </div>
                <div className="mono path-break">
                  launch_package_status={summary.observability.controlled_pilot_window_record.launch_package.status || "-"} launch_package_ready=
                  {String(summary.observability.controlled_pilot_window_record.launch_package.launch_package_ready ?? false)} launch_package_path=
                  {summary.observability.controlled_pilot_window_record.launch_package.path || "-"}
                </div>
                <div className="mono path-break">
                  commands={summary.observability.controlled_pilot_window_record.launch_package.operator_command_count ?? 0} roles=
                  {summary.observability.controlled_pilot_window_record.launch_package.pilot_role_count ?? 0} sources=
                  {summary.observability.controlled_pilot_window_record.launch_package.source_count ?? 0}
                </div>
                <div className="mono path-break">
                  rollback_required={String(summary.observability.controlled_pilot_window_record.rollback_required)} external_expansion_requires_new_manual_go_no_go=
                  {String(summary.observability.controlled_pilot_window_record.external_expansion_requires_new_manual_go_no_go)}
                </div>
                <div className="mono path-break">
                  business_data_written={String(summary.observability.controlled_pilot_window_record.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_window_record.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_window_record.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  auto_approved={String(summary.observability.controlled_pilot_window_record.auto_approved)} auto_closed=
                  {String(summary.observability.controlled_pilot_window_record.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_window_record.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_window_record.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Controlled pilot window status (read only)</h2>
            {!summary.observability.controlled_pilot_window_status ? (
              <div className="empty">no controlled pilot window status summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.controlled_pilot_window_status.status} window_opened=
                  {String(summary.observability.controlled_pilot_window_status.window.opened ?? false)} window_id=
                  {summary.observability.controlled_pilot_window_status.window.window_id || "-"}
                </div>
                <div className="mono path-break">
                  operations={summary.observability.controlled_pilot_window_status.operations_summary.status || "-"} health=
                  {summary.observability.controlled_pilot_window_status.operations_summary.health_status || "-"} deployment_ok=
                  {String(summary.observability.controlled_pilot_window_status.operations_summary.deployment_ok ?? false)}
                </div>
                <div className="mono path-break">
                  deployment_errors=
                  {summary.observability.controlled_pilot_window_status.operations_summary.deployment_error_count ?? 0} deployment_warnings=
                  {summary.observability.controlled_pilot_window_status.operations_summary.deployment_warning_count ?? 0}
                </div>
                <div className="mono path-break">
                  gate={summary.observability.controlled_pilot_window_status.operations_summary.launch_gate_status || "-"} gate_ready=
                  {String(summary.observability.controlled_pilot_window_status.operations_summary.launch_gate_ready ?? false)} package=
                  {summary.observability.controlled_pilot_window_status.operations_summary.launch_package_status || "-"} package_ready=
                  {String(summary.observability.controlled_pilot_window_status.operations_summary.launch_package_ready ?? false)}
                </div>
                <div className="mono path-break">
                  window_record={summary.observability.controlled_pilot_window_status.window.status || "-"} launch_package=
                  {summary.observability.controlled_pilot_window_status.window.launch_package_status || "-"} rollback_required=
                  {String(summary.observability.controlled_pilot_window_status.window.rollback_required ?? false)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.controlled_pilot_window_status.latest_report_present)} report_dir=
                  {summary.observability.controlled_pilot_window_status.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.controlled_pilot_window_status.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.controlled_pilot_window_status.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  business_data_written={String(summary.observability.controlled_pilot_window_status.business_data_written)} audit_data_written=
                  {String(summary.observability.controlled_pilot_window_status.audit_data_written)} metrics_data_written=
                  {String(summary.observability.controlled_pilot_window_status.metrics_data_written)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.controlled_pilot_window_status.missing_conditions.join(" | ") || "-"}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing status (read only)</h2>
            {!summary.observability.production_landing_status ? (
              <div className="empty">no production landing status summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_status.status} controlled_pilot_ready=
                  {String(summary.observability.production_landing_status.controlled_pilot_ready)} ready_domains=
                  {summary.observability.production_landing_status.ready_domain_count}/
                  {summary.observability.production_landing_status.domain_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_status.latest_report_present)} report_dir=
                  {summary.observability.production_landing_status.report_dir}
                </div>
                <div className="mono path-break">
                  blocked_domains={summary.observability.production_landing_status.blocked_domains.join(",") || "-"}
                </div>
                <div className="mono path-break">
                  blockers={summary.observability.production_landing_status.blockers.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  next_commands={summary.observability.production_landing_status.next_commands.join(" | ") || "-"}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_status.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.production_landing_status.secret_plaintext_output)}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing text quality (read only)</h2>
            {!summary.observability.production_landing_text_quality ? (
              <div className="empty">no production landing text quality summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_text_quality.status} checked_files=
                  {summary.observability.production_landing_text_quality.checked_file_count} blocked_files=
                  {summary.observability.production_landing_text_quality.blocked_file_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_text_quality.latest_report_present)} report_dir=
                  {summary.observability.production_landing_text_quality.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_text_quality.public_production_direct_launch} auto_approved=
                  {String(summary.observability.production_landing_text_quality.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_text_quality.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_text_quality.secret_plaintext_output)}
                </div>
                {summary.observability.production_landing_text_quality.files.length === 0 ? (
                  <div className="empty">no text quality file rows</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>file</th>
                          <th>status</th>
                          <th>exists</th>
                          <th>secret</th>
                          <th>markers</th>
                          <th>missing</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_text_quality.files.map((item) => (
                          <tr key={item.path}>
                            <td className="mono path-break">{item.path}</td>
                            <td>{item.status}</td>
                            <td>{String(item.exists)}</td>
                            <td>{String(item.secret_like_detected)}</td>
                            <td className="mono path-break">{item.mojibake_markers.join(",") || "-"}</td>
                            <td className="mono path-break">{item.missing_conditions.join(" | ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing evidence freshness (read only)</h2>
            {!summary.observability.production_landing_evidence_freshness ? (
              <div className="empty">no production landing evidence freshness summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_evidence_freshness.status} worktree_clean=
                  {String(summary.observability.production_landing_evidence_freshness.worktree_clean)} stale_sources=
                  {summary.observability.production_landing_evidence_freshness.stale_source_count}/
                  {summary.observability.production_landing_evidence_freshness.source_count}
                </div>
                <div className="mono path-break">
                  current_commit={summary.observability.production_landing_evidence_freshness.current_commit || "-"}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_evidence_freshness.latest_report_present)} report_dir=
                  {summary.observability.production_landing_evidence_freshness.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_evidence_freshness.public_production_direct_launch} auto_approved=
                  {String(summary.observability.production_landing_evidence_freshness.auto_approved)} auto_closed=
                  {String(summary.observability.production_landing_evidence_freshness.auto_closed)} secret_plaintext_output=
                  {String(summary.observability.production_landing_evidence_freshness.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  missing_conditions=
                  {summary.observability.production_landing_evidence_freshness.missing_conditions.join(" | ") || "-"}
                </div>
                {summary.observability.production_landing_evidence_freshness.sources.length === 0 ? (
                  <div className="empty">no evidence freshness source rows</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>source</th>
                          <th>status</th>
                          <th>present</th>
                          <th>head</th>
                          <th>secret</th>
                          <th>missing</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_evidence_freshness.sources.map((item) => (
                          <tr key={item.source_id}>
                            <td className="mono path-break">{item.source_id}</td>
                            <td>{item.status}</td>
                            <td>{String(item.present)}</td>
                            <td>{String(item.commit_matches_head)}</td>
                            <td>{String(item.secret_like_detected)}</td>
                            <td className="mono path-break">{item.missing_conditions.join(" | ") || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Xiaomi LLM preflight (process env only)</h2>
            {!summary.observability.production_landing_xiaomi_llm_preflight ? (
              <div className="empty">no Xiaomi LLM preflight summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_xiaomi_llm_preflight.status} api_key_env=
                  {summary.observability.production_landing_xiaomi_llm_preflight.api_key_env} api_key_present=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.api_key_present)}
                </div>
                <div className="mono path-break">
                  model={summary.observability.production_landing_xiaomi_llm_preflight.real_llm_model} base_url=
                  {summary.observability.production_landing_xiaomi_llm_preflight.real_llm_base_url}
                </div>
                <div className="mono path-break">
                  execute_network_check=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.execute_network_check)} network_check_executed=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.network_check_executed)} real_llm_executed=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.real_llm_executed)}
                </div>
                <div className="mono path-break">
                  network_check_requested=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.network_check_requested)}{" "}
                  network_check_allowed=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.network_check_allowed)}{" "}
                  safe_next_action={summary.observability.production_landing_xiaomi_llm_preflight.safe_next_action || "-"}
                </div>
                {summary.observability.production_landing_xiaomi_llm_preflight.acceptance_blockers.length === 0 ? (
                  <div className="empty">no acceptance blockers</div>
                ) : (
                  <div className="mono path-break">
                    acceptance_blockers=
                    {summary.observability.production_landing_xiaomi_llm_preflight.acceptance_blockers.join(" | ")}
                  </div>
                )}
                <div className="mono path-break">
                  env_file_written={String(summary.observability.production_landing_xiaomi_llm_preflight.env_file_written)} local_env_modified=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.local_env_modified)} secret_plaintext_output=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  report_present=
                  {String(summary.observability.production_landing_xiaomi_llm_preflight.latest_report_present)} report_dir=
                  {summary.observability.production_landing_xiaomi_llm_preflight.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_landing_xiaomi_llm_preflight.public_production_direct_launch}
                </div>
                {summary.observability.production_landing_xiaomi_llm_preflight.warnings.length === 0 ? (
                  <div className="empty">no warnings</div>
                ) : (
                  <div className="mono path-break">
                    warnings={summary.observability.production_landing_xiaomi_llm_preflight.warnings.join(" | ")}
                  </div>
                )}
                {summary.observability.production_landing_xiaomi_llm_preflight.errors.length === 0 ? (
                  <div className="empty">no errors</div>
                ) : (
                  <div className="mono path-break">
                    errors={summary.observability.production_landing_xiaomi_llm_preflight.errors.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Operations console landing smoke (read only)</h2>
            {!summary.observability.operations_console_landing_smoke ? (
              <div className="empty">no operations console landing smoke summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.operations_console_landing_smoke.status} execute=
                  {String(summary.observability.operations_console_landing_smoke.execute)} page_http_status=
                  {String(summary.observability.operations_console_landing_smoke.page_http_status ?? "-")} summary_http_status=
                  {String(summary.observability.operations_console_landing_smoke.summary_http_status ?? "-")} backend_summary_http_status=
                  {String(summary.observability.operations_console_landing_smoke.backend_summary_http_status ?? "-")}
                </div>
                <div className="mono path-break">
                  preflight_status={summary.observability.operations_console_landing_smoke.preflight_status || "-"} network_check_requested=
                  {String(summary.observability.operations_console_landing_smoke.network_check_requested)} network_check_allowed=
                  {String(summary.observability.operations_console_landing_smoke.network_check_allowed)}
                </div>
                <div className="mono path-break">
                  safe_next_action={summary.observability.operations_console_landing_smoke.safe_next_action || "-"} blocker_action_present=
                  {String(summary.observability.operations_console_landing_smoke.blocker_action_present)} blocker_safe_next_action=
                  {summary.observability.operations_console_landing_smoke.blocker_safe_next_action || "-"}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.operations_console_landing_smoke.latest_report_present)} report_dir=
                  {summary.observability.operations_console_landing_smoke.report_dir}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.operations_console_landing_smoke.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.operations_console_landing_smoke.secret_plaintext_output)}
                </div>
                {summary.observability.operations_console_landing_smoke.acceptance_blockers.length === 0 ? (
                  <div className="empty">no acceptance blockers</div>
                ) : (
                  <div className="mono path-break">
                    acceptance_blockers=
                    {summary.observability.operations_console_landing_smoke.acceptance_blockers.join(" | ")}
                  </div>
                )}
                {summary.observability.operations_console_landing_smoke.blocker_acceptance_blockers.length === 0 ? (
                  <div className="empty">no blocker acceptance blockers</div>
                ) : (
                  <div className="mono path-break">
                    blocker_acceptance_blockers=
                    {summary.observability.operations_console_landing_smoke.blocker_acceptance_blockers.join(" | ")}
                  </div>
                )}
                {summary.observability.operations_console_landing_smoke.missing_conditions.length === 0 ? (
                  <div className="empty">no missing conditions</div>
                ) : (
                  <div className="mono path-break">
                    missing_conditions=
                    {summary.observability.operations_console_landing_smoke.missing_conditions.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Business system input packet (read only)</h2>
            {!summary.observability.business_system_input_packet ? (
              <div className="empty">no business input packet summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.business_system_input_packet.status} ready_for_real_read_smoke=
                  {String(summary.observability.business_system_input_packet.ready_for_real_read_smoke)} missing_count=
                  {summary.observability.business_system_input_packet.missing_condition_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.business_system_input_packet.latest_report_present)} report_dir=
                  {summary.observability.business_system_input_packet.report_dir}
                </div>
                <div className="mono path-break">
                  owners=
                  {Object.entries(summary.observability.business_system_input_packet.owner_inputs_present)
                    .map(([key, value]) => `${key}:${String(value)}`)
                    .join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  config_enabled={String(Boolean(summary.observability.business_system_input_packet.config.enabled))} read_only=
                  {String(Boolean(summary.observability.business_system_input_packet.config.read_only))} write_enabled=
                  {String(Boolean(summary.observability.business_system_input_packet.config.write_enabled))} base_url_present=
                  {String(Boolean(summary.observability.business_system_input_packet.config.base_url_present))} token_present=
                  {String(Boolean(summary.observability.business_system_input_packet.config.token_present))}
                </div>
                <div className="mono path-break">
                  local_env_template=
                  {summary.observability.business_system_input_packet.local_env_template_lines.slice(0, 8).join(" ; ") ||
                    "-"}
                </div>
                <div className="mono path-break">
                  manual_checklist=
                  {summary.observability.business_system_input_packet.manual_input_checklist
                    .map((item) => item.id)
                    .join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  recommended_commands=
                  {summary.observability.business_system_input_packet.recommended_commands.join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  business_write_executed=
                  {String(summary.observability.business_system_input_packet.business_write_executed)} business_data_written=
                  {String(summary.observability.business_system_input_packet.business_data_written)} public_production_direct_launch=
                  {summary.observability.business_system_input_packet.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.business_system_input_packet.secret_plaintext_output)}
                </div>
                {summary.observability.business_system_input_packet.missing_conditions.length === 0 ? (
                  <div className="empty">no missing conditions</div>
                ) : (
                  <div className="mono path-break">
                    missing_conditions=
                    {summary.observability.business_system_input_packet.missing_conditions.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Business system read smoke (read only)</h2>
            {!summary.observability.business_system_read_smoke ? (
              <div className="empty">no business read smoke summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.business_system_read_smoke.status} execute=
                  {String(summary.observability.business_system_read_smoke.execute)} read_only=
                  {String(summary.observability.business_system_read_smoke.read_only)} ready_for_execute=
                  {String(summary.observability.business_system_read_smoke.env_profile.ready_for_execute)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.business_system_read_smoke.latest_report_present)} report_dir=
                  {summary.observability.business_system_read_smoke.report_dir}
                </div>
                <div className="mono path-break">
                  business_system_connected=
                  {String(summary.observability.business_system_read_smoke.business_system_connected)} business_read_executed=
                  {String(summary.observability.business_system_read_smoke.business_read_executed)} business_write_executed=
                  {String(summary.observability.business_system_read_smoke.business_write_executed)} business_data_written=
                  {String(summary.observability.business_system_read_smoke.business_data_written)}
                </div>
                <div className="mono path-break">
                  approval_bypassed={String(summary.observability.business_system_read_smoke.approval_bypassed)} audit_bypassed=
                  {String(summary.observability.business_system_read_smoke.audit_bypassed)} public_production_direct_launch=
                  {summary.observability.business_system_read_smoke.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.business_system_read_smoke.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  next_action={summary.observability.business_system_read_smoke.env_profile.next_action || "-"} env=
                  {summary.observability.business_system_read_smoke.env_profile.required_env.slice(0, 8).join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  auth_mode={summary.observability.business_system_read_smoke.env_profile.auth_mode || "-"} public_production_gap=
                  {String(summary.observability.business_system_read_smoke.env_profile.public_production_gap ?? true)}
                </div>
                <div className="mono path-break">
                  safe_commands=
                  {Object.values(summary.observability.business_system_read_smoke.env_profile.safe_commands ?? {})
                    .slice(0, 3)
                    .join(" ; ") || "-"}
                </div>
                {summary.observability.business_system_read_smoke.missing_conditions.length === 0 ? (
                  <div className="empty">no missing conditions</div>
                ) : (
                  <div className="mono path-break">
                    missing_conditions={summary.observability.business_system_read_smoke.missing_conditions.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Business system production readiness (read only)</h2>
            {!summary.observability.business_system_production_readiness ? (
              <div className="empty">no business production readiness summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.business_system_production_readiness.status} read_only=
                  {String(summary.observability.business_system_production_readiness.read_only)} missing_count=
                  {summary.observability.business_system_production_readiness.missing_condition_count}
                </div>
                <div className="mono path-break">
                  report_present=
                  {String(summary.observability.business_system_production_readiness.latest_report_present)} report_dir=
                  {summary.observability.business_system_production_readiness.report_dir}
                </div>
                <div className="mono path-break">
                  latest_smoke={summary.observability.business_system_production_readiness.latest_business_smoke.status} read_executed=
                  {String(
                    summary.observability.business_system_production_readiness.latest_business_smoke
                      .business_read_executed,
                  )} local_mock=
                  {String(
                    summary.observability.business_system_production_readiness.latest_business_smoke
                      .local_business_mock_used,
                  )}
                </div>
                <div className="mono path-break">
                  owners=
                  {Object.entries(summary.observability.business_system_production_readiness.owner_inputs_present)
                    .map(([key, value]) => `${key}:${String(value)}`)
                    .join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  business_write_executed=
                  {String(summary.observability.business_system_production_readiness.business_write_executed)} business_data_written=
                  {String(summary.observability.business_system_production_readiness.business_data_written)} public_production_direct_launch=
                  {summary.observability.business_system_production_readiness.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.business_system_production_readiness.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  required_inputs=
                  {summary.observability.business_system_production_readiness.required_inputs
                    .map((item) => item.id)
                    .join(" ; ") || "-"}
                </div>
                {summary.observability.business_system_production_readiness.missing_conditions.length === 0 ? (
                  <div className="empty">no missing conditions</div>
                ) : (
                  <div className="mono path-break">
                    missing_conditions=
                    {summary.observability.business_system_production_readiness.missing_conditions.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing env check (read only)</h2>
            {!summary.observability.production_landing_env_check ? (
              <div className="empty">no production landing env check summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_env_check.status} env_file_present=
                  {String(summary.observability.production_landing_env_check.env_file_present)} ready_domains=
                  {summary.observability.production_landing_env_check.ready_domain_count}/
                  {summary.observability.production_landing_env_check.domain_count} blocked_domains=
                  {summary.observability.production_landing_env_check.blocked_domain_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_env_check.latest_report_present)} report_dir=
                  {summary.observability.production_landing_env_check.report_dir}
                </div>
                <div className="mono path-break">
                  staging_smoke={summary.observability.production_landing_env_check.staging_smoke_command}
                </div>
                <div className="mono path-break">
                  business_smoke={summary.observability.production_landing_env_check.business_smoke_command} public_production_direct_launch=
                  {summary.observability.production_landing_env_check.public_production_direct_launch}
                </div>
                {summary.observability.production_landing_env_check.blocked_domain_summaries.length === 0 ? (
                  <div className="empty">no blocked env domains</div>
                ) : (
                  <div className="mono path-break">
                    blocked_domain_summary=
                    {summary.observability.production_landing_env_check.blocked_domain_summaries
                      .map(
                        (item) =>
                          `${item.domain_id}: blocker=${item.blocker_reason || "-"} next=${item.next_action || "-"} missing=${
                            item.missing_keys.join(",") || "-"
                          } placeholder=${item.placeholder_keys.join(",") || "-"} mismatch=${
                            item.mismatch_keys.join(",") || "-"
                          }`,
                      )
                      .join(" | ")}
                  </div>
                )}
                {summary.observability.production_landing_env_check.domains.length === 0 ? (
                  <div className="empty">no env check domains</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>domain</th>
                          <th>ready</th>
                          <th>missing</th>
                          <th>placeholder</th>
                          <th>mismatch</th>
                          <th>blocker</th>
                          <th>next_action</th>
                          <th>command</th>
                          <th>keys</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_landing_env_check.domains.map((item) => (
                          <tr key={item.domain_id}>
                            <td className="mono path-break">{item.domain_id}</td>
                            <td>{String(item.ready_for_execute)}</td>
                            <td>{item.missing_count}</td>
                            <td>{item.placeholder_count}</td>
                            <td>{item.mismatch_count}</td>
                            <td className="mono path-break">{item.blocker_reason || "-"}</td>
                            <td className="mono path-break">{item.next_action || "-"}</td>
                            <td className="mono path-break">{item.command_after_fill || "-"}</td>
                            <td className="mono path-break">
                              missing={item.missing_keys.join(",") || "-"} | placeholder=
                              {item.placeholder_keys.join(",") || "-"} | mismatch={item.mismatch_keys.join(",") || "-"} |
                              required={item.required_env_keys.join(",") || "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing execution gate (read only)</h2>
            {!summary.observability.production_landing_execution_gate ? (
              <div className="empty">no production landing execution gate summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_execution_gate.status} execution_allowed=
                  {String(summary.observability.production_landing_execution_gate.execution_allowed)} env_file_present=
                  {String(summary.observability.production_landing_execution_gate.env_file_present)}
                </div>
                <div className="mono path-break">
                  ready_domains={summary.observability.production_landing_execution_gate.ready_domain_count}/
                  {summary.observability.production_landing_execution_gate.requested_domain_count} blocked_domains=
                  {summary.observability.production_landing_execution_gate.blocked_domain_count}
                </div>
                <div className="mono path-break">
                  blocked={summary.observability.production_landing_execution_gate.blocked_domains.join(",") || "-"}
                </div>
                <div className="mono path-break">
                  commands={summary.observability.production_landing_execution_gate.safe_runner_commands.join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  real_smoke_executed={String(summary.observability.production_landing_execution_gate.real_smoke_executed)}
                  business_smoke_executed=
                  {String(summary.observability.production_landing_execution_gate.business_smoke_executed)}
                  public_production_direct_launch=
                  {summary.observability.production_landing_execution_gate.public_production_direct_launch}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production landing env runner (read only)</h2>
            {!summary.observability.production_landing_env_runner ? (
              <div className="empty">no production landing env runner summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_landing_env_runner.status} action=
                  {summary.observability.production_landing_env_runner.action || "-"} return_code=
                  {String(summary.observability.production_landing_env_runner.return_code)}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_landing_env_runner.latest_report_present)} report_dir=
                  {summary.observability.production_landing_env_runner.report_dir}
                </div>
                <div className="mono path-break">
                  env_file_present={String(summary.observability.production_landing_env_runner.env_file_present)} env_key_count=
                  {summary.observability.production_landing_env_runner.env_key_count} command=
                  {summary.observability.production_landing_env_runner.command || "-"}
                </div>
                <div className="mono path-break">
                  child_status={summary.observability.production_landing_env_runner.child_status || "-"} child_ready=
                  {summary.observability.production_landing_env_runner.child_summary.ready_domain_count}/
                  {summary.observability.production_landing_env_runner.child_summary.domain_count} child_secret_plaintext_output=
                  {String(summary.observability.production_landing_env_runner.child_summary.secret_plaintext_output)}
                </div>
                <div className="mono path-break">
                  stdout={summary.observability.production_landing_env_runner.stdout.slice(0, 4).join(" ; ") || "-"}
                </div>
                <div className="mono path-break">
                  stderr={summary.observability.production_landing_env_runner.stderr.slice(0, 4).join(" ; ") || "-"} public_production_direct_launch=
                  {summary.observability.production_landing_env_runner.public_production_direct_launch}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Real production environment checklist (read only)</h2>
            {!summary.observability.real_production_environment_checklist ? (
              <div className="empty">no real production environment checklist summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.real_production_environment_checklist.status} domains=
                  {summary.observability.real_production_environment_checklist.domain_count} report_present=
                  {String(summary.observability.real_production_environment_checklist.latest_report_present)}
                </div>
                <div className="mono path-break">
                  report_dir={summary.observability.real_production_environment_checklist.report_dir} public_production_direct_launch=
                  {summary.observability.real_production_environment_checklist.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.real_production_environment_checklist.secret_plaintext_output)}
                </div>
                {summary.observability.real_production_environment_checklist.domains.length === 0 ? (
                  <div className="empty">no checklist domains</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>domain</th>
                          <th>status</th>
                          <th>missing</th>
                          <th>safe command</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.real_production_environment_checklist.domains.map((item) => (
                          <tr key={item.domain_id}>
                            <td className="mono path-break">{item.domain_id}</td>
                            <td>{item.status}</td>
                            <td className="mono path-break">{item.missing_conditions.join(" | ") || "none"}</td>
                            <td className="mono path-break">
                              {summary.observability.real_production_environment_checklist?.next_commands[item.domain_id] ??
                                "-"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Real integration staging smoke (read only)</h2>
            {!summary.observability.real_integration_staging_smoke ? (
              <div className="empty">no real integration staging smoke summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.real_integration_staging_smoke.status} execute_requested=
                  {String(summary.observability.real_integration_staging_smoke.execute_requested)} read_only=
                  {String(summary.observability.real_integration_staging_smoke.read_only)} execution_mode=
                  {summary.observability.real_integration_staging_smoke.execution_mode}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.real_integration_staging_smoke.latest_report_present)} report_dir=
                  {summary.observability.real_integration_staging_smoke.report_dir}
                </div>
                <div className="mono path-break">
                  database_connected={String(summary.observability.real_integration_staging_smoke.database_connected)} redis_connected=
                  {String(summary.observability.real_integration_staging_smoke.redis_connected)} external_mcp_connected=
                  {String(summary.observability.real_integration_staging_smoke.external_mcp_connected)} real_llm_executed=
                  {String(summary.observability.real_integration_staging_smoke.real_llm_executed)}
                </div>
                <div className="mono path-break">
                  ready_domains={summary.observability.real_integration_staging_smoke.preflight_summary.ready_domain_count}/
                  {summary.observability.real_integration_staging_smoke.preflight_summary.domain_count} all_ready=
                  {String(
                    summary.observability.real_integration_staging_smoke.preflight_summary
                      .all_requested_domains_ready_for_execute,
                  )} public_production_direct_launch=
                  {summary.observability.real_integration_staging_smoke.public_production_direct_launch}
                </div>
                {summary.observability.real_integration_staging_smoke.preflight_summary.domains.length === 0 ? (
                  <div className="empty">no preflight domains</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>domain</th>
                          <th>status</th>
                          <th>ready</th>
                          <th>missing</th>
                          <th>required env</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.real_integration_staging_smoke.preflight_summary.domains.map((item) => (
                          <tr key={item.domain_id}>
                            <td className="mono path-break">{item.domain_id}</td>
                            <td>{item.status}</td>
                            <td>{String(item.ready_for_execute)}</td>
                            <td>{item.missing_count}</td>
                            <td className="mono path-break">
                              {item.required_env.slice(0, 8).join(" ; ")}
                              {item.next_action ? ` | ${item.next_action}` : ""}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production runtime smoke (read only)</h2>
            {!summary.observability.production_runtime_smoke ? (
              <div className="empty">no runtime smoke summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_runtime_smoke.status} endpoint_checks=
                  {summary.observability.production_runtime_smoke.endpoint_check_count} operations_contract=
                  {summary.observability.production_runtime_smoke.operations_contract_status}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_runtime_smoke.latest_report_present)} report_dir=
                  {summary.observability.production_runtime_smoke.report_dir}
                </div>
                <div className="mono path-break">
                  frontend_build={summary.observability.production_runtime_smoke.frontend_build_status} frontend_build_executed=
                  {String(summary.observability.production_runtime_smoke.frontend_build_executed)} bootstrap=
                  {summary.observability.production_runtime_smoke.bootstrap_status}
                </div>
                <div className="mono path-break">
                  business_system_connected=
                  {String(summary.observability.production_runtime_smoke.business_system_connected)} public_production_direct_launch=
                  {summary.observability.production_runtime_smoke.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.production_runtime_smoke.secret_plaintext_output)}
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Frontend production build (read only)</h2>
            {!summary.observability.frontend_production_build ? (
              <div className="empty">no frontend build summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.frontend_production_build.status} execute=
                  {String(summary.observability.frontend_production_build.execute)} build_executed=
                  {String(summary.observability.frontend_production_build.build_executed)} return_code=
                  {String(summary.observability.frontend_production_build.return_code ?? "-")}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.frontend_production_build.latest_report_present)} report_dir=
                  {summary.observability.frontend_production_build.report_dir}
                </div>
                <div className="mono path-break">
                  frontend_dir={String(summary.observability.frontend_production_build.frontend_dir_present)} package_json=
                  {String(summary.observability.frontend_production_build.package_json_present)} node_modules=
                  {String(summary.observability.frontend_production_build.node_modules_present)}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.frontend_production_build.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.frontend_production_build.secret_plaintext_output)}
                </div>
                {summary.observability.frontend_production_build.missing_conditions.length === 0 ? (
                  <div className="empty">no missing conditions</div>
                ) : (
                  <div className="mono path-break">
                    missing_conditions={summary.observability.frontend_production_build.missing_conditions.join(" | ")}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Production pilot bootstrap (read only)</h2>
            {!summary.observability.production_pilot_bootstrap ? (
              <div className="empty">no bootstrap summary</div>
            ) : (
              <div className="stack">
                <div className="mono path-break">
                  status={summary.observability.production_pilot_bootstrap.status} local_service=
                  {summary.observability.production_pilot_bootstrap.local_service_status} evidence_count=
                  {summary.observability.production_pilot_bootstrap.evidence_count}
                </div>
                <div className="mono path-break">
                  report_present={String(summary.observability.production_pilot_bootstrap.latest_report_present)} report_dir=
                  {summary.observability.production_pilot_bootstrap.report_dir}
                </div>
                <div className="mono path-break">
                  real_llm={String(summary.observability.production_pilot_bootstrap.real_llm_executed)} postgres=
                  {String(summary.observability.production_pilot_bootstrap.database_connected)} redis=
                  {String(summary.observability.production_pilot_bootstrap.redis_connected)} mcp=
                  {String(summary.observability.production_pilot_bootstrap.external_mcp_connected)} migration=
                  {String(summary.observability.production_pilot_bootstrap.migration_executed)}
                </div>
                <div className="mono path-break">
                  business_system=
                  {String(summary.observability.production_pilot_bootstrap.business_system_connected)} business_read=
                  {String(summary.observability.production_pilot_bootstrap.business_read_executed)} business_write=
                  {String(summary.observability.production_pilot_bootstrap.business_write_executed)} business_data_written=
                  {String(summary.observability.production_pilot_bootstrap.business_data_written)}
                </div>
                <div className="mono path-break">
                  auth_rbac=
                  {String(summary.observability.production_pilot_bootstrap.auth_rbac_acceptance_passed)} auth=
                  {String(summary.observability.production_pilot_bootstrap.auth_enabled)} rbac=
                  {String(summary.observability.production_pilot_bootstrap.rbac_enabled)} jwt_token_issued=
                  {String(summary.observability.production_pilot_bootstrap.jwt_token_issued)}
                </div>
                <div className="mono path-break">
                  signoff_closeout_passed=
                  {String(summary.observability.production_pilot_bootstrap.signoff_closeout_passed)} final_verification_passed=
                  {String(summary.observability.production_pilot_bootstrap.final_verification_passed)} pilot_evidence_bundle_passed=
                  {String(summary.observability.production_pilot_bootstrap.pilot_evidence_bundle_passed)}
                </div>
                <div className="mono path-break">
                  operations_console_smoke_status=
                  {summary.observability.production_pilot_bootstrap.operations_console_smoke_status}
                </div>
                <div className="mono path-break">
                  frontend_build_passed=
                  {String(summary.observability.production_pilot_bootstrap.frontend_build_passed)} frontend_build_executed=
                  {String(summary.observability.production_pilot_bootstrap.frontend_build_executed)} frontend_build_return_code=
                  {String(summary.observability.production_pilot_bootstrap.frontend_build_return_code ?? "-")}
                </div>
                <div className="mono path-break">
                  runtime_smoke_passed=
                  {String(summary.observability.production_pilot_bootstrap.runtime_smoke_passed)} runtime_smoke_endpoint_checks=
                  {summary.observability.production_pilot_bootstrap.runtime_smoke_endpoint_check_count}
                </div>
                <div className="mono path-break">
                  public_production_direct_launch=
                  {summary.observability.production_pilot_bootstrap.public_production_direct_launch} secret_plaintext_output=
                  {String(summary.observability.production_pilot_bootstrap.secret_plaintext_output)}
                </div>

                {summary.observability.production_pilot_bootstrap.evidence_runs.length === 0 ? (
                  <div className="empty">run python scripts/production_pilot_bootstrap.py to generate first report</div>
                ) : (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>evidence_id</th>
                          <th>status</th>
                          <th>json_path</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.observability.production_pilot_bootstrap.evidence_runs.map((item) => (
                          <tr key={item.evidence_id}>
                            <td className="mono path-break">{item.evidence_id}</td>
                            <td>{item.status}</td>
                            <td className="mono path-break">{item.json_path || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <div className="table-wrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>domain</th>
                        <th>next command</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summary.observability.production_pilot_bootstrap.next_commands).map(
                        ([domain, commands]) => (
                          <tr key={domain}>
                            <td className="mono path-break">{domain}</td>
                            <td className="mono path-break">{commands.find((item) => item.startsWith("python ")) ?? "-"}</td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">v4 evidence readiness (read only)</h2>
            <div className="stack">
              <div className="mono path-break">
                mode={summary.observability.v4_evidence?.mode ?? "-"} total_json_reports=
                {summary.observability.v4_evidence?.total_json_report_count ?? 0}
              </div>
              <div className="mono path-break">
                boundary={compactJson(summary.observability.v4_evidence?.boundary ?? {})}
              </div>
            </div>

            {!summary.observability.v4_evidence ? (
              <div className="empty">no v4 evidence summary</div>
            ) : Object.keys(summary.observability.v4_evidence.entries).length === 0 ? (
              <div className="empty">no v4 evidence entries</div>
            ) : (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>evidence_key</th>
                      <th>entry_state</th>
                      <th>json_reports</th>
                      <th>directory_exists</th>
                      <th>runbook_path</th>
                      <th>directory</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(summary.observability.v4_evidence.entries).map(([key, item]) => (
                      <tr key={key}>
                        <td className="mono path-break">{key}</td>
                        <td>{v4EvidenceEntryState(item.directory_exists, item.json_report_count)}</td>
                        <td>{item.json_report_count}</td>
                        <td>{String(item.directory_exists)}</td>
                        <td className="mono path-break">{item.runbook_path}</td>
                        <td className="mono path-break">{item.directory}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">v4 evidence status semantics</h2>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>status</th>
                    <th>operator_meaning</th>
                    <th>production_launch</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>skipped</td>
                    <td>missing input or opt-in condition; no false success</td>
                    <td>No-Go</td>
                  </tr>
                  <tr>
                    <td>blocked</td>
                    <td>boundary violation, failed upstream, secret-like input, or unsafe execution marker</td>
                    <td>No-Go</td>
                  </tr>
                  <tr>
                    <td>partial</td>
                    <td>manual review required; evidence may be ready for review but not approved</td>
                    <td>Manual-Review</td>
                  </tr>
                  <tr>
                    <td>success</td>
                    <td>local script completed its bounded check; not a production acceptance claim</td>
                    <td>Manual-Review</td>
                  </tr>
                </tbody>
              </table>
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
