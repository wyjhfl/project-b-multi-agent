import { apiFetch } from "@/lib/api/client";
import type { ApprovalSummary } from "@/types/api";

export interface ApprovalItem {
  approval_id: string;
  task_id: string;
  status: string;
  risk_level?: string;
  created_at?: string;
}

export async function getApprovalSummary(): Promise<ApprovalSummary> {
  return apiFetch<ApprovalSummary>("/approvals/summary");
}

export async function listPendingApprovals(limit = 20): Promise<ApprovalItem[]> {
  const query = new URLSearchParams({ status: "pending", limit: String(limit) });
  return apiFetch<ApprovalItem[]>(`/approvals?${query.toString()}`);
}
