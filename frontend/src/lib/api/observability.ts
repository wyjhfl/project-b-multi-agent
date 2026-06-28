import { apiFetch } from "@/lib/api/client";
import type { TrajectoryResponse } from "@/types/api";

export async function getTaskTrajectory(taskId: string): Promise<TrajectoryResponse> {
  return apiFetch<TrajectoryResponse>(`/observability/tasks/${taskId}/trajectory`);
}
