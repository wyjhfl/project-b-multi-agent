import { apiFetch } from "@/lib/api/client";
import type {
  NL2SQLExecuteRequest,
  NL2SQLExecuteResult,
  NL2SQLPreviewRequest,
  NL2SQLPreviewResult,
} from "@/types/api";

export async function previewNl2sql(payload: NL2SQLPreviewRequest): Promise<NL2SQLPreviewResult> {
  return apiFetch<NL2SQLPreviewResult>("/nl2sql/preview", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function executeNl2sql(payload: NL2SQLExecuteRequest): Promise<NL2SQLExecuteResult> {
  return apiFetch<NL2SQLExecuteResult>("/nl2sql/execute", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
