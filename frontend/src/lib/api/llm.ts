import { apiFetch } from "@/lib/api/client";
import type { LlmPreflightResponse } from "@/types/api";

export async function getLlmPreflight(networkCheck = false): Promise<LlmPreflightResponse> {
  const query = networkCheck ? "?network_check=true" : "";
  return apiFetch<LlmPreflightResponse>(`/llm/preflight${query}`);
}
