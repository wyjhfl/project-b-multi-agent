import { apiFetch } from "@/lib/api/client";
import type {
  TaskCreatePayload,
  TaskCreateResponse,
  TaskItem,
  TraceResponse,
} from "@/types/api";

export async function listTasks(limit = 20): Promise<TaskItem[]> {
  const query = new URLSearchParams({ limit: String(limit) });
  return apiFetch<TaskItem[]>(`/tasks?${query.toString()}`);
}

export async function getTask(taskId: string): Promise<TaskItem> {
  return apiFetch<TaskItem>(`/tasks/${taskId}`);
}

export async function getTaskTrace(taskId: string): Promise<TraceResponse> {
  return apiFetch<TraceResponse>(`/tasks/${taskId}/trace`);
}

export async function createTask(payload: TaskCreatePayload): Promise<TaskCreateResponse> {
  return apiFetch<TaskCreateResponse>("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
