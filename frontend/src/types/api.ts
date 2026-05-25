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
