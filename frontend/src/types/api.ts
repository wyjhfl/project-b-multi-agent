export type TaskStatus =
  | "created"
  | "running"
  | "completed"
  | "failed"
  | "waiting_approval"
  | "cancelled"
  | string;

export interface TaskItem {
  task_id: string;
  query: string;
  mode?: string;
  status: TaskStatus;
  result?: Record<string, unknown> | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface TaskCreatePayload {
  query: string;
  mode: string;
  generator: string;
  provider?: string;
  fallback_to_mock: boolean;
}

export interface TaskCreateResponse {
  task_id: string;
  query: string;
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  persistence_error?: string | null;
}

export interface TraceEvent {
  event_id?: string;
  event_type: string;
  actor?: string;
  detail?: Record<string, unknown>;
  timestamp: string;
}

export interface TraceResponse {
  task_id: string;
  events: TraceEvent[];
}

export interface RuntimeSummary {
  task_count?: number;
  success_count?: number;
  failed_count?: number;
  waiting_approval_count?: number;
  cancelled_count?: number;
  unknown_status_count?: number;
  tool_call_count?: number;
  tool_failure_count?: number;
  total_prompt_tokens?: number;
  total_completion_tokens?: number;
  total_cost?: number;
  avg_task_latency_ms?: number;
  llm_budget?: Record<string, unknown>;
  llm_cache?: Record<string, unknown>;
}

export interface TasksSummary {
  task_count: number;
  success_count: number;
  failed_count: number;
  waiting_approval_count: number;
  cancelled_count: number;
  unknown_status_count?: number;
  avg_task_latency_ms: number;
  by_mode?: Record<string, { count: number; success_count: number; failed_count: number }>;
}

export interface ToolsSummary {
  tool_call_count: number;
  tool_failure_count: number;
  retry_count?: number;
  avg_latency_ms?: number;
  by_tool?: Record<
    string,
    {
      call_count: number;
      failure_count: number;
      retry_count?: number;
      avg_latency_ms?: number;
    }
  >;
}

export interface CostSummary {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost: number;
  by_mode?: Record<
    string,
    {
      prompt_tokens: number;
      completion_tokens: number;
      cost: number;
    }
  >;
  by_day?: Record<
    string,
    {
      prompt_tokens: number;
      completion_tokens: number;
      cost: number;
    }
  >;
}

export interface ApprovalSummary {
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  expired_count: number;
}

export interface ApprovalItem {
  approval_id: string;
  task_id: string;
  tool_name?: string;
  action?: string;
  risk_level?: string;
  status: string;
  requested_at?: string;
  created_at?: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_reason?: string | null;
  payload?: Record<string, unknown> | null;
  already_decided?: boolean;
  already_resumed?: boolean;
  decision_error?: string;
  error?: string;
}

export interface ApprovalTimelineEvent {
  event_type: string;
  timestamp: string;
  detail?: Record<string, unknown> | null;
}

export interface ApprovalContext {
  approval?: ApprovalItem;
  task?: TaskItem | null;
  payload?: Record<string, unknown> | null;
  timeline: ApprovalTimelineEvent[];
  resume_status?: string | null;
  can_approve: boolean;
  can_reject: boolean;
  can_resume: boolean;
  error?: string;
}

export interface ApprovalDecisionPayload {
  decided_by: string;
  reason: string;
  auto_resume?: boolean;
}

export interface ApprovalDecisionResult extends ApprovalItem {
  resume_result?: Record<string, unknown> | null;
  cancellation_result?: Record<string, unknown> | null;
}

export interface ApprovalResumeResult {
  approval_id: string;
  already_resumed?: boolean;
  resume_result?: Record<string, unknown> | null;
  error?: string;
  resumed?: boolean;
}

export interface AuditEventDetail {
  [key: string]: unknown;
}

export interface AuditEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  actor?: string;
  task_id?: string | null;
  approval_id?: string | null;
  tool_name?: string | null;
  action?: string;
  outcome?: string;
  reason?: string | null;
  severity?: string | null;
  detail?: AuditEventDetail;
  error?: string;
}

export interface AuditFilters {
  event_type?: string;
  actor?: string;
  task_id?: string;
  approval_id?: string;
  outcome?: string;
  severity?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
}

export interface AuditExportFilters {
  event_type?: string;
  task_id?: string;
  severity?: string;
  outcome?: string;
  limit?: number;
  format?: "jsonl";
}

export interface ToolSpec {
  tool_name: string;
  description: string;
  source: string;
  server_name?: string | null;
  risk_level: string;
  permission_scope: string;
  is_local?: boolean;
}

export interface ToolCallResult {
  call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
  status: string;
  success: boolean;
  latency_ms: number;
  error?: string | null;
}

export interface GuardrailsFinding {
  type?: string;
  masked_value?: string;
  risk_level?: string;
  span?: unknown;
  [key: string]: unknown;
}

export interface GuardrailsResult {
  allowed?: boolean;
  action?: string;
  reason?: string;
  risk_level?: string;
  findings?: GuardrailsFinding[];
  sanitized_text?: string;
  [key: string]: unknown;
}

export interface NL2SQLPreviewRequest {
  query: string;
  generator?: string;
  provider?: string;
  fallback_to_mock?: boolean;
}

export interface LlmAcceptanceSummary {
  mode: string;
  provider: string;
  model: string;
  real_call_attempted: boolean;
  real_call_succeeded: boolean;
  fallback_used: boolean;
  fallback_reason: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  latency_ms: number;
  cache_hit: boolean;
  budget_action: string;
  request_id: string;
  error_type: string;
  warnings: string[];
}

export interface NL2SQLPreviewResult {
  selected_tables: string[];
  fallback: boolean;
  sql: string;
  guard_allowed: boolean;
  guard_reason?: string;
  reasoning: string;
  confidence: number;
  generator_used: string;
  provider_used?: string | null;
  fallback_used: boolean;
  fallback_reason?: string | null;
  warnings: string[];
  guardrails?: Record<string, GuardrailsResult | unknown> | null;
  provider_metadata?: Record<string, unknown> | null;
  budget_status?: Record<string, unknown> | null;
  acceptance_summary?: LlmAcceptanceSummary | null;
}

export type NL2SQLExecuteRequest = NL2SQLPreviewRequest;

export interface NL2SQLExecuteResult extends NL2SQLPreviewResult {
  execution?: {
    sql?: string;
    success?: boolean;
    row_count?: number;
    rows?: Record<string, unknown>[] | unknown[];
    error?: string | null;
    [key: string]: unknown;
  } | null;
  formatted_result?: {
    summary?: string;
    columns?: string[];
    rows?: Record<string, unknown>[] | unknown[];
    row_count?: number;
    truncated?: boolean;
    [key: string]: unknown;
  } | null;
  chart_spec?: Record<string, unknown> | null;
}

export interface LlmPreflightResponse {
  allowed: boolean;
  status: string;
  provider: string;
  model: string;
  base_url: string;
  api_key_env: string;
  api_key_present: boolean;
  network_check_allowed: boolean;
  network_check_requested: boolean;
  network_check_executed: boolean;
  checks: Array<{
    name: string;
    ok: boolean;
    detail: string;
  }>;
  warnings: string[];
  errors: string[];
  latency_ms: number;
}

export interface LlmPilotReportListItem {
  report_id: string;
  generated_at: string;
  provider: string;
  model: string;
  scenario: string;
  outcome: string;
  request_id: string;
  real_call_succeeded: boolean;
  fallback_used: boolean;
  cost: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  audit_event_id: string;
  audit_event_type: string;
  path: string;
  name: string;
}

export interface LlmPilotReportDetail {
  report_id: string;
  generated_at: string;
  provider: string;
  model: string;
  scenario: string;
  outcome: string;
  request_id: string;
  real_call_attempted: boolean;
  real_call_succeeded: boolean;
  fallback_used: boolean;
  fallback_reason: string;
  budget_action: string;
  cache_hit: boolean;
  latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost: number;
  error_type: string;
  evidence_links?: Record<string, unknown> | null;
  observability?: Record<string, unknown> | null;
  evidence_notes?: string[] | null;
  cases?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface OperationsSummary {
  generated_at: string;
  mode: string;
  health: {
    status: string;
    service: string;
    version: string;
    storage_backend?: string;
    auth_enabled?: boolean;
    rbac_enabled?: boolean;
    redis?: Record<string, unknown>;
  };
  deployment: {
    ok: boolean;
    environment: string;
    error_count: number;
    warning_count: number;
    errors: string[];
    warnings: string[];
    check_count: number;
  };
  runtime_metrics: RuntimeSummary & {
    llm_budget?: Record<string, unknown>;
    llm_cache?: Record<string, unknown>;
  };
  task_approval: {
    task_count: number;
    approval_count: number;
    pending_approval_count: number;
    task_status_counts: Record<string, number>;
    recent_tasks: Array<{
      task_id: string;
      status: string;
      mode: string;
      created_at: string;
    }>;
    recent_approvals: Array<{
      approval_id: string;
      task_id: string;
      status: string;
      risk_level: string;
      tool_name: string;
      requested_at: string;
    }>;
  };
  audit: {
    event_count: number;
    recent_events: Array<{
      event_id: string;
      event_type: string;
      created_at: string;
      actor: string;
      outcome: string;
      severity: string;
      task_id: string;
      request_id: string;
      summary: string;
      detail_redacted: Record<string, unknown>;
    }>;
  };
  pilot_reports: {
    report_dir: string;
    directory_exists: boolean;
    total_reports: number;
    reports: Array<{
      report_id: string;
      generated_at: string;
      scenario: string;
      outcome: string;
      request_id: string;
      fallback_used: boolean;
      cost: number;
      total_tokens: number;
      audit_event_id: string;
      name: string;
    }>;
  };
  demo_evidence: {
    mode: string;
    runbook_path: string;
    script_path: string;
    tip: string;
  };
}

