import { apiFetch } from "@/lib/api/client";
import type { RuntimeSummary, TaskSummary } from "@/types/api";

export async function getRuntimeSummary(): Promise<RuntimeSummary> {
  return apiFetch<RuntimeSummary>("/metrics/runtime");
}

export async function getTaskSummary(): Promise<TaskSummary> {
  return apiFetch<TaskSummary>("/metrics/tasks/summary");
}
