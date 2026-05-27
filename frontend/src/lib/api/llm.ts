import { apiFetch } from "@/lib/api/client";
import type { LlmPilotReportDetail, LlmPilotReportListItem, LlmPreflightResponse } from "@/types/api";

export async function getLlmPreflight(networkCheck = false): Promise<LlmPreflightResponse> {
  const query = networkCheck ? "?network_check=true" : "";
  return apiFetch<LlmPreflightResponse>(`/llm/preflight${query}`);
}

export async function listPilotReports(): Promise<LlmPilotReportListItem[]> {
  return apiFetch<LlmPilotReportListItem[]>("/llm/pilot/reports");
}

export async function getPilotReport(reportId: string): Promise<LlmPilotReportDetail> {
  return apiFetch<LlmPilotReportDetail>(`/llm/pilot/reports/${encodeURIComponent(reportId)}`);
}
