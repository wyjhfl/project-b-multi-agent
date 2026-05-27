import { apiFetch } from "@/lib/api/client";
import type { OperationsSummary } from "@/types/api";

export async function getOperationsSummary(): Promise<OperationsSummary> {
  return apiFetch<OperationsSummary>("/operations/summary");
}
