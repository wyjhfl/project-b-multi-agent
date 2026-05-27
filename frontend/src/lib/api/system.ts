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

export interface OidcStatus {
  enabled: boolean;
  issuer_configured: boolean;
  client_id_configured: boolean;
  redirect_uri_configured: boolean;
  client_secret_env: string;
  client_secret_present: boolean;
  scopes: string[];
  role_claim: string;
  default_role: string;
  allowed_roles: string[];
  errors: string[];
  warnings: string[];
}

export async function getHealthStatus(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}

export async function getOidcStatus(): Promise<OidcStatus> {
  return apiFetch<OidcStatus>("/auth/oidc/status");
}
