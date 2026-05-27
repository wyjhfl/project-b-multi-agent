import { apiFetch } from "@/lib/api/client";
import type {
  CostSummary,
  RuntimeSummary,
  TasksSummary,
  ToolsSummary,
} from "@/types/api";

export async function getRuntimeSummary(): Promise<RuntimeSummary> {
  return apiFetch<RuntimeSummary>("/metrics/runtime");
}

export async function getTasksSummary(): Promise<TasksSummary> {
  return apiFetch<TasksSummary>("/metrics/tasks/summary");
}

export async function getToolsSummary(): Promise<ToolsSummary> {
  return apiFetch<ToolsSummary>("/metrics/tools/summary");
}

export async function getCostSummary(): Promise<CostSummary> {
  return apiFetch<CostSummary>("/metrics/cost/summary");
}
