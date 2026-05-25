import { apiFetch } from "@/lib/api/client";
import type {
  ApprovalContext,
  ApprovalDecisionPayload,
  ApprovalDecisionResult,
  ApprovalItem,
  ApprovalResumeResult,
  ApprovalSummary,
} from "@/types/api";

export async function getApprovalSummary(): Promise<ApprovalSummary> {
  return apiFetch<ApprovalSummary>("/approvals/summary");
}

export async function listPendingApprovals(limit = 20): Promise<ApprovalItem[]> {
  return listApprovals("pending", limit);
}

export async function listApprovals(status?: string, limit = 20): Promise<ApprovalItem[]> {
  const query = new URLSearchParams();
  if (status && status !== "all") {
    query.set("status", status);
  }
  query.set("limit", String(limit));
  return apiFetch<ApprovalItem[]>(`/approvals?${query.toString()}`);
}

export async function getApproval(approvalId: string): Promise<ApprovalItem> {
  return apiFetch<ApprovalItem>(`/approvals/${approvalId}`);
}

export async function getApprovalContext(approvalId: string): Promise<ApprovalContext> {
  return apiFetch<ApprovalContext>(`/approvals/${approvalId}/context`);
}

export async function approveApproval(
  approvalId: string,
  payload: ApprovalDecisionPayload,
): Promise<ApprovalDecisionResult> {
  return apiFetch<ApprovalDecisionResult>(`/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function rejectApproval(
  approvalId: string,
  payload: ApprovalDecisionPayload,
): Promise<ApprovalDecisionResult> {
  return apiFetch<ApprovalDecisionResult>(`/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resumeApproval(approvalId: string): Promise<ApprovalResumeResult> {
  return apiFetch<ApprovalResumeResult>(`/approvals/${approvalId}/resume`, {
    method: "POST",
  });
}
