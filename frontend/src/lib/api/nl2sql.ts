import { apiFetch, ApiError, buildUrl } from "@/lib/api/client";
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

export interface NL2SQLStreamHandlers {
  onStage?: (stage: string) => void;
  onSqlDelta?: (delta: string) => void;
  onGuard?: (allowed: boolean, reason: string) => void;
  onExecution?: (execution: Record<string, unknown>) => void;
  onDone?: (result: NL2SQLExecuteResult) => void;
  onError?: (reason: string) => void;
}

function dispatchSseEvent(rawEvent: string, handlers: NL2SQLStreamHandlers): void {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of rawEvent.split("\n")) {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  }
  if (dataLines.length === 0) {
    return;
  }
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(dataLines.join("\n")) as Record<string, unknown>;
  } catch {
    return;
  }
  switch (eventName) {
    case "stage":
      handlers.onStage?.(String(data.stage ?? ""));
      break;
    case "sql_delta":
      handlers.onSqlDelta?.(String(data.delta ?? ""));
      break;
    case "guard":
      handlers.onGuard?.(Boolean(data.allowed), String(data.reason ?? ""));
      break;
    case "execution":
      handlers.onExecution?.(data);
      break;
    case "done":
      handlers.onDone?.(data as unknown as NL2SQLExecuteResult);
      break;
    case "error":
      handlers.onError?.(String(data.reason ?? "stream error"));
      break;
    default:
      break;
  }
}

export async function streamNl2sql(
  payload: NL2SQLExecuteRequest,
  handlers: NL2SQLStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(buildUrl("/nl2sql/stream"), {
    method: "POST",
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(`流式接口请求失败：${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    let sepIndex = buffer.indexOf("\n\n");
    while (sepIndex !== -1) {
      const rawEvent = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      dispatchSseEvent(rawEvent, handlers);
      sepIndex = buffer.indexOf("\n\n");
    }
  }
}
