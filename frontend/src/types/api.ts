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
  tool_call_count?: number;
  tool_failure_count?: number;
  total_cost?: number;
  llm_budget?: Record<string, unknown>;
  llm_cache?: Record<string, unknown>;
}

export interface TaskSummary {
  task_count: number;
  success_count: number;
  failed_count: number;
  waiting_approval_count: number;
  cancelled_count: number;
  avg_task_latency_ms: number;
  by_mode?: Record<string, { count: number; success_count: number; failed_count: number }>;
}

export interface ApprovalSummary {
  pending_count: number;
  approved_count: number;
  rejected_count: number;
  expired_count: number;
}
