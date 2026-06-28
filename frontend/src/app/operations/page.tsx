import Link from "next/link";
import { getOperationsSummary } from "@/lib/api/operations";
import { formatDateTime } from "@/lib/status";

function boolLabel(value: boolean): string {
  return value ? "Yes" : "No";
}

function compactList(value?: string[]): string {
  return value && value.length > 0 ? value.join(" | ") : "none";
}

type LandingDecisionTone = "ready" | "warning" | "blocked";

function landingTone(value?: string | boolean | null): LandingDecisionTone {
  if (value === true) {
    return "ready";
  }
  const normalized = String(value ?? "").toLowerCase();
  if (["ready", "success", "go", "healthy", "true", "showcase-ready", "ok"].includes(normalized)) {
    return "ready";
  }
  if (["no-go", "failed", "blocked", "false"].includes(normalized)) {
    return "blocked";
  }
  return "warning";
}

function LandingDecisionCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: LandingDecisionTone;
}) {
  return (
    <div className={`landing-decision-card ${tone}`}>
      <div className="landing-decision-label">{label}</div>
      <div className="landing-decision-value">{value || "-"}</div>
      <div className="landing-decision-detail">{detail}</div>
    </div>
  );
}

function EvidenceRow({
  label,
  status,
  detail,
}: {
  label: string;
  status?: string | boolean | null;
  detail: string;
}) {
  const tone = landingTone(status);
  return (
    <div className="landing-evidence-row">
      <span className={`landing-dot ${tone}`} aria-hidden="true" />
      <div>
        <div className="landing-evidence-label">{label}</div>
        <div className="landing-evidence-detail">{detail}</div>
      </div>
    </div>
  );
}

function landingActionLabel(action: string): string {
  const labels: Record<string, string> = {
    run_interview_demo_readiness: "Run the read-only interview readiness check.",
    start_local_demo: "Start the local Docker demo.",
    run_demo_smoke: "Run local demo smoke checks.",
    inspect_multi_agent_trajectory: "Inspect Trace and Multi-Agent Trajectory in Observability.",
    keep_public_production_direct_launch_no_go_until_real_business_system_acceptance:
      "Keep public production direct launch at No-Go until real business-system acceptance is complete.",
  };
  return labels[action] ?? action.replaceAll("_", " ");
}

function landingSourceLabel(source?: string | null): string {
  const labels: Record<string, string> = {
    showcase_runtime_summary: "showcase runtime summary",
    default: "fallback",
  };
  return labels[source ?? ""] ?? String(source ?? "fallback").replaceAll("_", " ");
}

function landingDecisionValue(value?: string | boolean | null): string {
  if (value === true) {
    return "Ready";
  }
  if (value === false) {
    return "Review";
  }
  const labels: Record<string, string> = {
    "Manual-Review": "Manual Review",
    "No-Go": "No-Go",
    Go: "Go",
    success: "success",
    ready: "ready",
  };
  return labels[String(value ?? "")] ?? String(value ?? "-");
}

export default async function OperationsOverviewPage() {
  let summary: Awaited<ReturnType<typeof getOperationsSummary>> | null = null;
  let errorText = "";

  try {
    summary = await getOperationsSummary();
  } catch (error) {
    errorText = error instanceof Error ? error.message : "failed to load operations overview";
  }

  const landingCommandCenter = summary?.observability.landing_command_center;
  const controlledPilotDecision = landingCommandCenter?.controlled_internal_pilot ?? "-";
  const publicProductionDecision = landingCommandCenter?.public_production_direct_launch ?? "No-Go";
  const precommitReady = landingCommandCenter?.precommit_ready ?? false;
  const actionInputCount = landingCommandCenter?.action_required_input_count ?? 0;
  const actionPackStatus = landingCommandCenter?.action_pack_status ?? "-";
  const landingNextActions = landingCommandCenter?.next_actions ?? [];
  const landingReviewReasons = landingCommandCenter?.run_packet_missing_conditions ?? [];
  const landingOperatorGuidance = landingCommandCenter?.operator_guidance;

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">Operations Overview (Read Only)</h1>
        <p className="page-subtitle">
          Read-only observability panel for runtime health, deployment guard, metrics, approvals, audit, and showcase
          readiness. Default fake/offline. No real LLM call. No secrets.
        </p>
      </header>

      {errorText ? (
        <section className="section card">
          <div className="empty">service unavailable: {errorText}</div>
          <div className="mono muted path-break">hint: start backend service and retry /operations</div>
        </section>
      ) : !summary || !landingCommandCenter ? (
        <section className="section card">
          <div className="empty">no summary data available</div>
        </section>
      ) : (
        <>
          <section className="section landing-command-grid">
            <div className="landing-decision-panel">
              <div>
                <div className="eyebrow">Landing Command Center</div>
                <h2 className="landing-title">Controlled pilot decision view</h2>
                <p className="landing-copy">
                  Current-version showcase view for pilot explanation, evidence review, and launch boundary tracking.
                </p>
              </div>
              <div className="landing-decision-cards">
                <LandingDecisionCard
                  label="Controlled Pilot"
                  value={landingDecisionValue(controlledPilotDecision)}
                  detail={`Gate source: ${landingSourceLabel(landingCommandCenter.controlled_internal_pilot_source)}`}
                  tone={landingTone(controlledPilotDecision)}
                />
                <LandingDecisionCard
                  label="Public Launch"
                  value={landingDecisionValue(publicProductionDecision)}
                  detail="Public production boundary"
                  tone={landingTone(publicProductionDecision)}
                />
                <LandingDecisionCard
                  label="Precommit Ready"
                  value={precommitReady ? "Ready" : "Review"}
                  detail={`action inputs=${actionInputCount}`}
                  tone={landingTone(precommitReady)}
                />
                <LandingDecisionCard
                  label="Action Pack"
                  value={actionPackStatus}
                  detail="Showcase repository state"
                  tone={landingTone(actionPackStatus)}
                />
              </div>
            </div>

            <div className="landing-evidence-grid">
              <section className="landing-panel">
                <h2 className="card-title">Evidence Chain</h2>
                <div className="landing-evidence-list">
                  <EvidenceRow
                    label="Runtime"
                    status={landingCommandCenter.evidence.runtime.status}
                    detail={landingCommandCenter.evidence.runtime.detail}
                  />
                  <EvidenceRow
                    label="Deployment Guard"
                    status={landingCommandCenter.evidence.deployment.status}
                    detail={landingCommandCenter.evidence.deployment.detail}
                  />
                  <EvidenceRow
                    label="CI Test Contract"
                    status={landingCommandCenter.evidence.tests.status}
                    detail={landingCommandCenter.evidence.tests.detail}
                  />
                  <EvidenceRow
                    label="Text Quality"
                    status={landingCommandCenter.evidence.text_quality.status}
                    detail={`blocked files=${landingCommandCenter.evidence.text_quality.blocked_file_count}`}
                  />
                </div>
              </section>

              <section className="landing-panel">
                <h2 className="card-title">Next Actions</h2>
                <div className="landing-next-actions">
                  {landingNextActions.map((action) => (
                    <div key={action} className="landing-action-item">
                      {landingActionLabel(action)}
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </section>

          <section className="section landing-command-grid">
            <div className="landing-panel landing-review-reasons">
              <h2 className="card-title">Review Reasons</h2>
              {landingReviewReasons.length === 0 ? (
                <div className="empty">no review reason reported</div>
              ) : (
                <ul className="landing-review-list">
                  {landingReviewReasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              )}
            </div>

            <div className="landing-panel">
              <h2 className="card-title">Operator Guidance</h2>
              {!landingOperatorGuidance ? (
                <div className="empty">operator guidance unavailable</div>
              ) : (
                <div className="landing-guidance-list">
                  {landingOperatorGuidance.commands.map((item) => (
                    <div key={item.id} className="landing-guidance-item">
                      <div className="landing-evidence-label">{item.label}</div>
                      <div className="mono path-break">{item.command}</div>
                      <div className="muted">safe_boundary={item.safe_boundary}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="section grid">
            <div className="card">
              <h2 className="card-title">Runtime</h2>
              <p className="metric">
                {summary.health.status} <span className="muted">version={summary.health.version}</span>
              </p>
              <p className="muted">
                storage={summary.health.storage_backend ?? "-"} auth={String(summary.health.auth_enabled)} rbac=
                {String(summary.health.rbac_enabled)}
              </p>
            </div>
            <div className="card">
              <h2 className="card-title">Deployment Guard</h2>
              <p className="metric">{summary.deployment.ok ? "ok" : "review"}</p>
              <p className="muted">
                errors={summary.deployment.error_count} warnings={summary.deployment.warning_count}
              </p>
            </div>
            <div className="card">
              <h2 className="card-title">Tasks / Approvals</h2>
              <p className="metric">
                {summary.task_approval.task_count} / {summary.task_approval.approval_count}
              </p>
              <p className="muted">pending approvals={summary.task_approval.pending_approval_count}</p>
            </div>
            <div className="card">
              <h2 className="card-title">Audit</h2>
              <p className="metric">{summary.audit.event_count}</p>
              <p className="muted">recent sanitized events</p>
            </div>
          </section>

          <section className="section grid">
            <div className="card">
              <h2 className="card-title">Current Docs</h2>
              <div className="mono path-break">{compactList(summary.observability.current_docs)}</div>
            </div>
            <div className="card">
              <h2 className="card-title">Current Scripts</h2>
              <div className="mono path-break">{compactList(summary.observability.current_scripts)}</div>
            </div>
          </section>

          <section className="section card">
            <h2 className="card-title">Recent Audit Events</h2>
            {summary.audit.recent_events.length === 0 ? (
              <div className="empty">no recent audit events</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Type</th>
                      <th>Outcome</th>
                      <th>Severity</th>
                      <th>Summary</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.audit.recent_events.map((event) => (
                      <tr key={event.event_id}>
                        <td>{formatDateTime(event.created_at)}</td>
                        <td>{event.event_type}</td>
                        <td>{event.outcome}</td>
                        <td>{event.severity}</td>
                        <td>{event.summary || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="section card">
            <h2 className="card-title">Boundary</h2>
            <div className="grid">
              <div>
                <div className="muted">public_production_direct_launch</div>
                <div className="mono">{publicProductionDecision}</div>
              </div>
              <div>
                <div className="muted">real_business_system_connected</div>
                <div className="mono">{boolLabel(landingCommandCenter.real_business_system_connected)}</div>
              </div>
              <div>
                <div className="muted">secret_plaintext_output</div>
                <div className="mono">{boolLabel(landingCommandCenter.secret_plaintext_output)}</div>
              </div>
            </div>
          </section>

          <p className="muted">
            Need the full API surface? Open <Link href="/tools">Tools</Link>, <Link href="/tasks">Tasks</Link>,{" "}
            <Link href="/approvals">Approvals</Link>, or <Link href="/audit">Audit</Link>.
          </p>
        </>
      )}
    </div>
  );
}
