import { apiFetch } from "@/lib/api/client";

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  storage_backend?: string;
  auth_enabled?: boolean;
  rbac_enabled?: boolean;
  redis?: Record<string, unknown>;
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}
