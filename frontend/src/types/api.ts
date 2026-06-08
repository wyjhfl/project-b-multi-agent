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

export interface V4EvidenceEntry {
  runbook_path: string;
  directory: string;
  directory_exists: boolean;
  json_report_count: number;
}

export interface V4EvidenceSummary {
  mode: string;
  entries: Record<string, V4EvidenceEntry>;
  total_json_report_count: number;
  boundary: {
    report_content_read: boolean;
    real_llm_executed: boolean;
    external_system_connected: boolean;
    auto_approved: boolean;
    auto_closed: boolean;
    [key: string]: boolean;
  };
}

export interface ProductionPilotBootstrapSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  local_service_status: string;
  evidence_count: number;
  execute_real_smoke: boolean;
  real_llm_executed: boolean;
  database_connected: boolean;
  redis_connected: boolean;
  external_mcp_connected: boolean;
  migration_executed: boolean;
  business_system_connected: boolean;
  business_read_executed: boolean;
  business_write_executed: boolean;
  business_data_written: boolean;
  auth_rbac_acceptance_passed: boolean;
  signoff_closeout_passed: boolean;
  final_verification_passed: boolean;
  pilot_evidence_bundle_passed: boolean;
  operations_console_smoke_status: string;
  frontend_build_passed: boolean;
  frontend_build_executed: boolean;
  frontend_build_return_code?: number | null;
  runtime_smoke_passed: boolean;
  runtime_smoke_endpoint_check_count: number;
  auth_enabled: boolean;
  rbac_enabled: boolean;
  jwt_token_issued: boolean;
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
  next_commands: Record<string, string[]>;
  evidence_runs: Array<{
    evidence_id: string;
    status: string;
    json_path: string;
  }>;
}

export interface FrontendProductionBuildSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  execute: boolean;
  build_executed: boolean;
  return_code?: number | null;
  frontend_dir_present: boolean;
  package_json_present: boolean;
  node_modules_present: boolean;
  missing_conditions: string[];
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
}

export interface ProductionRuntimeSmokeSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  endpoint_check_count: number;
  operations_contract_status: string;
  frontend_build_status: string;
  frontend_build_executed: boolean;
  bootstrap_status: string;
  business_system_connected: boolean;
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
}

export interface ProductionPilotSignoffSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  readiness_item_count: number;
  manual_signoff_required: boolean;
  manual_signoff_completed?: boolean;
  manual_signoff_record_present?: boolean;
  manual_signoff_package_status?: string;
  manual_signoff_roles?: string[];
  manual_signoff_decision?: string;
  manual_signoff_blockers?: string[];
  closure_evidence_summary: {
    latest_report: string;
    report_count: number;
    closure_item_count: number;
    review_ready_count: number;
    evidence_missing_count: number;
    evidence_incomplete_count: number;
    blocked_closure_count: number;
    evidence_readiness_summary: {
      local_evidence_available_count: number;
      runbook_only_count: number;
      missing_count: number;
      manual_review_required: boolean;
      auto_approved: boolean;
      auto_closed: boolean;
    };
  };
  auto_signed: boolean;
  auto_approved: boolean;
  secret_plaintext_output: boolean;
  recommendation: string;
  production_pilot: string;
  enterprise_landing_state: string;
  controlled_pilot_manual_review_ready: boolean;
  database_connected: boolean;
  redis_connected: boolean;
  external_mcp_connected: boolean;
  real_infra_ready: boolean;
  production_blockers: string[];
  public_production_direct_launch: string;
}

export interface BusinessSystemReadSmokeSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  execute: boolean;
  execution_requested: boolean;
  read_only: boolean;
  env_profile: {
    execution_requested: boolean;
    ready_for_execute: boolean;
    required_env: string[];
    auth_mode?: string;
    safe_commands?: Record<string, string>;
    present: Record<string, boolean>;
    public_production_gap?: boolean;
    next_action: string;
  };
  business_system_connected: boolean;
  business_read_executed: boolean;
  business_write_executed: boolean;
  business_data_written: boolean;
  approval_bypassed: boolean;
  audit_bypassed: boolean;
  missing_conditions: string[];
  secret_plaintext_output: boolean;
  business_system_read_smoke: string;
  public_production_direct_launch: string;
  manual_signoff_required: boolean;
}

export interface BusinessSystemInputPacketSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_for_real_read_smoke: boolean;
  owner_inputs_present: Record<string, boolean>;
  config: Record<string, unknown>;
  missing_conditions: string[];
  missing_condition_count: number;
  required_inputs: Array<{ id: string; env: string[]; description: string }>;
  local_env_template_lines: string[];
  manual_input_checklist: Array<{ id: string; env: string[]; description: string }>;
  recommended_commands: string[];
  business_write_executed: boolean;
  business_data_written: boolean;
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
}

export interface BusinessSystemProductionReadinessSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  read_only: boolean;
  owner_inputs_present: Record<string, boolean>;
  required_inputs: Array<{
    id: string;
    description: string;
    env: string;
    command: string;
  }>;
  latest_business_smoke: {
    latest_report_present: boolean;
    status: string;
    business_system_connected: boolean;
    business_read_executed: boolean;
    business_write_executed: boolean;
    business_data_written: boolean;
    local_business_mock_used: boolean;
    secret_plaintext_output: boolean;
  };
  missing_conditions: string[];
  missing_condition_count: number;
  business_write_executed: boolean;
  business_data_written: boolean;
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
}

export interface BusinessSystemLandingExecutionPackSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_for_real_read_smoke: boolean;
  real_read_smoke_complete: boolean;
  safe_next_action: string;
  recommended_next_command: string;
  recommended_commands: string[];
  manual_input_checklist: Array<{ id: string; env: string[]; description: string }>;
  missing_conditions: string[];
  missing_condition_count: number;
  missing_by_category: Record<string, string[]>;
  source_statuses: Record<string, string>;
  evidence_paths: Record<string, string>;
  owner_inputs_present: Record<string, boolean>;
  business_system_read_smoke: {
    status: string;
    business_system_connected: boolean;
    business_read_executed: boolean;
    business_write_executed: boolean;
    business_data_written: boolean;
    local_business_mock_used: boolean;
    secret_plaintext_output: boolean;
  };
  manual_signoff_required: boolean;
  business_write_executed: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
  secret_plaintext_output: boolean;
  public_production_direct_launch: string;
}

export interface RealIntegrationStagingSmokeSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  execute_requested: boolean;
  read_only: boolean;
  execution_mode: string;
  database_connected: boolean;
  redis_connected: boolean;
  external_mcp_connected: boolean;
  real_llm_executed: boolean;
  migration_executed: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
  secret_plaintext_output: boolean;
  preflight_summary: {
    ready_domain_count: number;
    domain_count: number;
    ready_domains: string[];
    blocked_domain_count: number;
    failed_domain_count: number;
    all_requested_domains_ready_for_execute: boolean;
    domains: Array<{
      domain_id: string;
      status: string;
      execution_allowed: boolean;
      execution_invoked: boolean;
      ready_for_execute: boolean;
      missing_count: number;
      env_present: Record<string, boolean>;
      required_env: string[];
      next_action: string;
    }>;
  };
  missing_conditions: string[];
  public_production_direct_launch: string;
}

export interface RealProductionEnvironmentChecklistSummary {
  mode: string;
  runbook_path: string;
  infra_smoke_runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  domain_count: number;
  domains: Array<{
    domain_id: string;
    status: string;
    owner: string;
    phase: string;
    missing_conditions: string[];
    manual_signoff_required: boolean;
    production_direct_launch: string;
  }>;
  next_commands: Record<string, string>;
  real_llm_executed?: boolean;
  database_connected?: boolean;
  redis_connected?: boolean;
  external_mcp_connected?: boolean;
  business_data_written?: boolean;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingActionPackSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  required_input_count: number;
  required_inputs: Array<{
    input_id: string;
    status: string;
    template: string;
    filled_record?: string;
    draft: string;
    required_domains: string;
    required_env: string;
    blocking_evidence_items?: Array<{
      item: string;
      source_status: string;
      missing_conditions: string[];
      acceptance_blockers?: string[];
      safe_next_action?: string;
      safe_commands: string[];
    }>;
    command_after_fill: string;
    promote_command_after_manual_fill?: string;
    process_env_only_llm_preflight_command: string;
  }>;
  recommended_commands: string[];
  template_status: Record<
    string,
    {
      path: string;
      exists: boolean;
      size_bytes: number;
    }
  >;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingBlockerResolutionSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  required_action_count: number;
  required_actions: string[];
  actions: Array<{
    action_id: string;
    status: string;
    owner: string;
    evidence: Record<string, string | string[]>;
    safe_commands: string[];
  }>;
  source_blocked_or_failed: string[];
  source_missing_conditions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingFinalVerificationSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  passed_count: number;
  requirement_count: number;
  missing_conditions: string[];
  requirements: Array<{
    requirement_id: string;
    passed: boolean;
    missing_conditions: string[];
  }>;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionPilotEvidenceBundleSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  controlled_pilot_ready: boolean;
  controlled_pilot: string;
  final_verification_passed_count: number;
  final_verification_requirement_count: number;
  missing_condition_count: number;
  missing_conditions: string[];
  sources: Record<
    string,
    {
      source_id: string;
      present: boolean;
      status: string;
      latest_json_path: string;
      generated_at: string;
      passed_count: number;
      requirement_count: number;
      missing_condition_count: number;
      open_gap_count: number;
      gap_count: number;
      domain_count: number;
      secret_plaintext_output: boolean;
      public_production_direct_launch: string;
      missing_conditions: string[];
      secret_detected: boolean;
    }
  >;
  next_actions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ControlledPilotLaunchGateSummary {
  mode: string;
  status: string;
  ready_for_controlled_pilot: boolean;
  controlled_pilot: string;
  public_production_direct_launch: string;
  manual_signoff_required: boolean;
  delivery_gate_status?: string;
  accepted_remaining_gaps?: string[];
  evidence_bundle_status: string;
  final_verification_status: string;
  signoff_closeout_status: string;
  bootstrap_status: string;
  final_verification_passed_count: number;
  final_verification_requirement_count: number;
  missing_condition_count: number;
  missing_conditions: string[];
  safe_next_action: string;
  operator_command: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ControlledPilotDeliveryGateSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  controlled_pilot_delivery_ready: boolean;
  enterprise_landing_scope: string;
  accepted_remaining_gaps: string[];
  missing_condition_count: number;
  missing_conditions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ControlledPilotRunPacketSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  run_packet_ready: boolean;
  controlled_internal_pilot: string;
  ready_scope: string;
  public_production_direct_launch: string;
  accepted_remaining_gaps: string[];
  real_production_remaining_gaps: string[];
  business_system_boundary: {
    connected?: boolean;
    read_executed?: boolean;
    write_executed?: boolean;
    business_data_written?: boolean;
    local_business_mock_used?: boolean;
    demo_business_system_used?: boolean;
    real_business_system_connected?: boolean;
  };
  safety_boundary: {
    read_only?: boolean;
    manual_signoff_required?: boolean;
    rollback_required?: boolean;
    external_expansion_requires_new_manual_go_no_go?: boolean;
    public_production_direct_launch?: string;
  };
  operator_commands: Record<string, string>;
  evidence_paths: Record<string, string>;
  source_statuses: Record<string, string>;
  missing_condition_count: number;
  missing_conditions: string[];
  secret_plaintext_output: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
}

export interface EvidenceArchiveSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  manifest_id: string;
  version: string;
  total_files: number;
  total_size_bytes: number;
  missing_expected_types: string[];
  latest_by_type: Record<
    string,
    {
      evidence_type: string;
      path: string;
      size_bytes: number;
      modified_at: string;
      extension: string;
    }
  >;
  retention_policy: {
    apply_mode: string;
    deletion_enabled: boolean;
    auto_cleanup_enabled: boolean;
  };
  boundary_declarations: string[];
  read_only: boolean;
  real_llm_executed: boolean;
}

export interface ControlledPilotStatusSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path: string;
  status: string;
  controlled_internal_pilot: string;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  blocking_reports: string[];
  public_production_gaps: string[];
  public_production_gap_count: number;
  source_statuses: Record<string, string>;
  operations_console_smoke_execute: boolean;
  runtime_smoke_passed: boolean;
}

export interface ControlledPilotOperatorPacketSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  controlled_internal_pilot: string;
  public_production_direct_launch: string;
  window_id: string;
  missing_condition_count: number;
  missing_conditions: string[];
  public_production_gaps: string[];
  public_production_gap_count: number;
  business_system_read_smoke: {
    status: string;
    business_system_connected: boolean;
    business_read_executed: boolean;
    auth_mode: string;
  };
  production_landing_evidence_freshness: {
    status: string;
    worktree_clean: boolean;
    source_count: number;
    stale_source_count: number;
    public_production_direct_launch: string;
  };
  evidence_paths: Record<string, string>;
  operator_command_count: number;
  pilot_role_count: number;
  rollback_required: boolean;
  external_expansion_requires_new_manual_go_no_go: boolean;
  secret_plaintext_output: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
}

export interface ControlledPilotConsoleVerifySummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  controlled_internal_pilot: string;
  public_production_direct_launch: string;
  backend_url: string;
  frontend_url: string;
  missing_condition_count: number;
  missing_conditions: string[];
  pid_file_present_after_verify: boolean;
  secret_plaintext_output: boolean;
  real_llm_executed: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
}

export interface ControlledPilotConsolePreflightSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_for_local_verify: boolean;
  recommended_command: string;
  backend_url: string;
  frontend_url: string;
  blocking_condition_count: number;
  blocking_conditions: string[];
  latest_verify_status: string;
  latest_verify_controlled_internal_pilot: string;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  real_llm_executed: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
}

export interface ControlledPilotLaunchPackageSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  launch_package_ready: boolean;
  controlled_pilot: string;
  public_production_direct_launch: string;
  manual_signoff_required: boolean;
  accepted_remaining_gaps?: string[];
  missing_condition_count: number;
  missing_conditions: string[];
  safe_next_action: string;
  operator_commands: string[];
  pilot_roles: Array<{
    role: string;
    responsibility: string;
  }>;
  launch_window: {
    scope?: string;
    public_production_direct_launch?: string;
    rollback_required?: boolean;
    external_expansion_requires_new_manual_go_no_go?: boolean;
  };
  sources: Record<
    string,
    {
      source_id: string;
      present: boolean;
      status: string;
      latest_json_path: string;
      generated_at: string;
      missing_conditions: string[];
      secret_detected: boolean;
      summary: Record<string, unknown>;
    }
  >;
  secret_plaintext_output: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ControlledPilotWindowRecordSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  window_id: string;
  opened: boolean;
  opened_by: string;
  confirm_open: string;
  controlled_pilot: string;
  public_production_direct_launch: string;
  manual_signoff_required: boolean;
  launch_package: {
    present?: boolean;
    status?: string;
    path?: string;
    launch_package_ready?: boolean;
    controlled_pilot?: string;
    public_production_direct_launch?: string;
    missing_condition_count?: number;
    safe_next_action?: string;
    operator_command_count?: number;
    pilot_role_count?: number;
    source_count?: number;
    secret_plaintext_output?: boolean;
  };
  missing_conditions: string[];
  missing_condition_count: number;
  rollback_required: boolean;
  external_expansion_requires_new_manual_go_no_go: boolean;
  secret_plaintext_output: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ControlledPilotWindowStatusSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  window: {
    present?: boolean;
    status?: string;
    path?: string;
    opened?: boolean;
    window_id?: string;
    opened_by?: string;
    controlled_pilot?: string;
    public_production_direct_launch?: string;
    missing_condition_count?: number;
    rollback_required?: boolean;
    launch_package_ready?: boolean;
    launch_package_status?: string;
    secret_plaintext_output?: boolean;
  };
  operations_summary: {
    status?: string;
    http_status?: number | null;
    health_status?: string;
    deployment_ok?: boolean;
    deployment_error_count?: number;
    deployment_warning_count?: number;
    controlled_pilot_window_status?: string;
    controlled_pilot_window_opened?: boolean;
    controlled_pilot_window_id?: string;
    launch_package_status?: string;
    launch_package_ready?: boolean;
    launch_gate_status?: string;
    launch_gate_ready?: boolean;
    public_production_direct_launch?: string;
  };
  missing_conditions: string[];
  missing_condition_count: number;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  business_data_written: boolean;
  audit_data_written: boolean;
  metrics_data_written: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingEnvCheckSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  env_file_present: boolean;
  ready_domain_count: number;
  blocked_domain_count: number;
  domain_count: number;
  domains: Array<{
    domain_id: string;
    ready_for_execute: boolean;
    blocker_reason: string;
    next_action: string;
    command_after_fill: string;
    required_env_keys: string[];
    missing_count: number;
    placeholder_count: number;
    mismatch_count: number;
    missing_keys: string[];
    placeholder_keys: string[];
    mismatch_keys: string[];
  }>;
  blocked_domain_summaries: Array<{
    domain_id: string;
    blocker_reason: string;
    next_action: string;
    missing_count: number;
    placeholder_count: number;
    mismatch_count: number;
    missing_keys: string[];
    placeholder_keys: string[];
    mismatch_keys: string[];
  }>;
  staging_smoke_command: string;
  business_smoke_command: string;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingEnvRunnerSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  action: string;
  env_file_present: boolean;
  env_key_count: number;
  command: string;
  return_code: number | null;
  child_status: string;
  child_summary: {
    status: string;
    ready_domain_count: number;
    domain_count: number;
    secret_plaintext_output: boolean;
  };
  stdout: string[];
  stderr: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingExecutionGateSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  env_file_present: boolean;
  requested_domains: string[];
  ready_domains: string[];
  blocked_domains: string[];
  requested_domain_count: number;
  ready_domain_count: number;
  blocked_domain_count: number;
  all_requested_domains_ready_for_execute: boolean;
  execution_allowed: boolean;
  real_smoke_executed: boolean;
  business_smoke_executed: boolean;
  domains: ProductionLandingEnvCheckSummary["domains"];
  safe_runner_commands: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingXiaomiLlmPreflightSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  api_key_env: string;
  api_key_present: boolean;
  real_llm_model: string;
  real_llm_base_url: string;
  execute_network_check: boolean;
  network_check_requested: boolean;
  network_check_allowed: boolean;
  network_check_executed: boolean;
  real_llm_executed: boolean;
  env_file_written: boolean;
  local_env_modified: boolean;
  safe_next_action: string;
  acceptance_blockers: string[];
  warnings: string[];
  errors: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface OperationsConsoleLandingSmokeSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  execute: boolean;
  page_http_status?: number | null;
  summary_http_status?: number | null;
  backend_summary_http_status?: number | null;
  preflight_status: string;
  network_check_requested: boolean;
  network_check_allowed: boolean;
  safe_next_action: string;
  acceptance_blockers: string[];
  blocker_action_present: boolean;
  blocker_safe_next_action: string;
  blocker_acceptance_blockers: string[];
  missing_conditions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingStatusSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  controlled_pilot_ready: boolean;
  ready_domain_count: number;
  domain_count: number;
  blocked_domains: string[];
  blockers: string[];
  next_commands: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
}

export interface ProductionLandingInputReadinessSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_input_count: number;
  required_input_count: number;
  missing_input_count: number;
  blocked_input_count: number;
  source_reports: Record<string, string>;
  resolved_paths: Record<string, string>;
  inputs: Array<{
    input_id: string;
    path: string;
    present: boolean;
    status: string;
    missing_conditions: string[];
    missing_count: number;
    ready_count: number;
    closure_item_count: number;
    base_url_present: boolean;
    token_present: boolean;
    database_connected: boolean;
    redis_connected: boolean;
    external_mcp_connected: boolean;
    real_infra_ready: boolean;
    read_only: boolean;
    write_enabled: boolean;
    secret_plaintext_output: boolean;
    auto_approved: boolean;
    auto_closed: boolean;
    next_action: string;
    command_after_fill: string;
    required_env: string[];
  }>;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ManualSignoffEvidenceAckStatusSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  recommended_accept_count: number;
  item_count: number;
  blocked_item_count: number;
  items: Array<{
    item: string;
    latest_report: string;
    report_present: boolean;
    source_status: string;
    recommended_accept: boolean;
    missing_conditions: string[];
    missing_count: number;
  }>;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ManualSignoffRecordValidationSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  signoff_record_present: boolean;
  ack_status: string;
  manual_signoff_completed: boolean;
  decision: string;
  roles: Array<{
    role: string;
    name_present: boolean;
    approved: boolean;
  }>;
  evidence_acknowledgements: Array<{
    item: string;
    accepted: boolean;
    latest_report: string;
    note_present: boolean;
  }>;
  missing_conditions: string[];
  missing_condition_count: number;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ManualSignoffRecordFillSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  signoff_record: string;
  filled: boolean;
  manual_signoff_completed: boolean;
  decision: string;
  missing_conditions: string[];
  missing_condition_count: number;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_signed: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ManualSignoffRecordPromoteSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  source_record?: string;
  target_record?: string;
  source_record_present: boolean;
  target_record_written: boolean;
  promoted: boolean;
  manual_signoff_completed: boolean;
  decision: string;
  missing_conditions: string[];
  missing_condition_count: number;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingSignoffCloseoutSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  final_status: string;
  signoff_record?: string;
  target_record?: string;
  target_record_written: boolean;
  steps: Array<{
    step_id: string;
    status: string;
    json_path: string;
    secret_plaintext_output: boolean;
  }>;
  missing_conditions: string[];
  missing_condition_count: number;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_signed: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingPreSignoffGateSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_for_manual_signoff: boolean;
  technical_evidence_ready: boolean;
  ack_ready: boolean;
  action_required_input_count: number;
  non_signoff_blockers: string[];
  non_signoff_blocker_count: number;
  signoff_only_missing_conditions: string[];
  status_blockers: string[];
  final_missing_conditions: string[];
  closeout_missing_conditions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_signed: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingSignoffReviewerPacketSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  ready_for_manual_signoff: boolean;
  technical_evidence_ready: boolean;
  non_signoff_blocker_count: number;
  ack_ready: boolean;
  missing_conditions: string[];
  missing_condition_count: number;
  recommended_closeout_command: string;
  evidence: Array<{
    source_id: string;
    status: string;
    latest_report_present: boolean;
    latest_json_path: string;
    secret_plaintext_output: boolean;
  }>;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_signed: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingTextQualitySummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  checked_file_count: number;
  blocked_file_count: number;
  files: Array<{
    path: string;
    exists: boolean;
    status: string;
    mojibake_markers: string[];
    secret_like_detected: boolean;
    missing_conditions: string[];
  }>;
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
}

export interface ProductionLandingEvidenceFreshnessSummary {
  mode: string;
  runbook_path: string;
  report_dir: string;
  directory_exists: boolean;
  latest_report_present: boolean;
  latest_json_path?: string;
  status: string;
  generated_at: string;
  current_commit: string;
  worktree_clean: boolean;
  source_count: number;
  stale_source_count: number;
  sources: Array<{
    source_id: string;
    present: boolean;
    status: string;
    generated_at: string;
    report_commit: string;
    commit_matches_head: boolean;
    secret_like_detected: boolean;
    missing_conditions: string[];
  }>;
  missing_conditions: string[];
  public_production_direct_launch: string;
  secret_plaintext_output: boolean;
  auto_approved: boolean;
  auto_closed: boolean;
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
  observability: {
    acceptance_snapshot_runbook_path: string;
    demo_artifact_runbook_path: string;
    artifact_default_dir: string;
    snapshot_default_dir: string;
    last_known_report_counts: {
      pilot_reports: number;
      audit_recent_events: number;
      v4_evidence_reports?: number;
      production_pilot_bootstrap_reports?: number;
      frontend_production_build_reports?: number;
      production_runtime_smoke_reports?: number;
      production_pilot_signoff_reports?: number;
      business_system_read_smoke_reports?: number;
      business_system_input_packet_reports?: number;
      business_system_production_readiness_reports?: number;
      business_system_landing_execution_pack_reports?: number;
      real_integration_staging_smoke_reports?: number;
      real_production_environment_checklist_reports?: number;
      production_landing_input_readiness_reports?: number;
      production_landing_env_check_reports?: number;
      production_landing_env_runner_reports?: number;
      production_landing_execution_gate_reports?: number;
      production_landing_action_pack_reports?: number;
      production_landing_blocker_resolution_reports?: number;
      production_landing_final_verification_reports?: number;
      production_pilot_evidence_bundle_reports?: number;
      controlled_pilot_delivery_gate_reports?: number;
      controlled_pilot_run_packet_reports?: number;
      controlled_pilot_launch_gate_reports?: number;
      controlled_pilot_launch_package_reports?: number;
      controlled_pilot_window_record_reports?: number;
      controlled_pilot_window_status_reports?: number;
      controlled_pilot_status_summary_reports?: number;
      controlled_pilot_operator_packet_reports?: number;
      controlled_pilot_console_preflight_reports?: number;
      controlled_pilot_console_verify_reports?: number;
      production_landing_xiaomi_llm_preflight_reports?: number;
      operations_console_landing_smoke_reports?: number;
      production_landing_status_reports?: number;
      manual_signoff_evidence_ack_status_reports?: number;
      manual_signoff_record_validation_reports?: number;
      manual_signoff_record_fill_reports?: number;
      production_landing_signoff_closeout_reports?: number;
      production_landing_pre_signoff_gate_reports?: number;
      production_landing_signoff_reviewer_packet_reports?: number;
      manual_signoff_record_promote_reports?: number;
      production_landing_text_quality_reports?: number;
      production_landing_evidence_freshness_reports?: number;
      evidence_archive_reports?: number;
    };
    production_pilot_bootstrap?: ProductionPilotBootstrapSummary;
    frontend_production_build?: FrontendProductionBuildSummary;
    production_runtime_smoke?: ProductionRuntimeSmokeSummary;
    production_pilot_signoff?: ProductionPilotSignoffSummary;
    business_system_read_smoke?: BusinessSystemReadSmokeSummary;
    business_system_input_packet?: BusinessSystemInputPacketSummary;
    business_system_production_readiness?: BusinessSystemProductionReadinessSummary;
    business_system_landing_execution_pack?: BusinessSystemLandingExecutionPackSummary;
    real_integration_staging_smoke?: RealIntegrationStagingSmokeSummary;
    real_production_environment_checklist?: RealProductionEnvironmentChecklistSummary;
    production_landing_input_readiness?: ProductionLandingInputReadinessSummary;
    production_landing_env_check?: ProductionLandingEnvCheckSummary;
    production_landing_env_runner?: ProductionLandingEnvRunnerSummary;
    production_landing_execution_gate?: ProductionLandingExecutionGateSummary;
    production_landing_action_pack?: ProductionLandingActionPackSummary;
    production_landing_blocker_resolution?: ProductionLandingBlockerResolutionSummary;
    production_landing_final_verification?: ProductionLandingFinalVerificationSummary;
    production_pilot_evidence_bundle?: ProductionPilotEvidenceBundleSummary;
    controlled_pilot_status_summary?: ControlledPilotStatusSummary;
    controlled_pilot_operator_packet?: ControlledPilotOperatorPacketSummary;
    controlled_pilot_console_preflight?: ControlledPilotConsolePreflightSummary;
    controlled_pilot_console_verify?: ControlledPilotConsoleVerifySummary;
    controlled_pilot_delivery_gate?: ControlledPilotDeliveryGateSummary;
    controlled_pilot_run_packet?: ControlledPilotRunPacketSummary;
    controlled_pilot_launch_gate?: ControlledPilotLaunchGateSummary;
    controlled_pilot_launch_package?: ControlledPilotLaunchPackageSummary;
    controlled_pilot_window_record?: ControlledPilotWindowRecordSummary;
    controlled_pilot_window_status?: ControlledPilotWindowStatusSummary;
    production_landing_xiaomi_llm_preflight?: ProductionLandingXiaomiLlmPreflightSummary;
    operations_console_landing_smoke?: OperationsConsoleLandingSmokeSummary;
    production_landing_status?: ProductionLandingStatusSummary;
    manual_signoff_evidence_ack_status?: ManualSignoffEvidenceAckStatusSummary;
    manual_signoff_record_validation?: ManualSignoffRecordValidationSummary;
    manual_signoff_record_fill?: ManualSignoffRecordFillSummary;
    production_landing_signoff_closeout?: ProductionLandingSignoffCloseoutSummary;
    production_landing_pre_signoff_gate?: ProductionLandingPreSignoffGateSummary;
    production_landing_signoff_reviewer_packet?: ProductionLandingSignoffReviewerPacketSummary;
    manual_signoff_record_promote?: ManualSignoffRecordPromoteSummary;
    production_landing_text_quality?: ProductionLandingTextQualitySummary;
    production_landing_evidence_freshness?: ProductionLandingEvidenceFreshnessSummary;
    evidence_archive?: EvidenceArchiveSummary;
    v4_evidence?: V4EvidenceSummary;
  };
  demo_evidence: {
    mode: string;
    runbook_path: string;
    script_path: string;
    tip: string;
  };
}

