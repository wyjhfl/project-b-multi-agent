import { apiFetch } from "@/lib/api/client";
import type { ToolCallResult, ToolSpec } from "@/types/api";

export async function listTools(): Promise<ToolSpec[]> {
  const tools = await apiFetch<ToolSpec[]>("/tools");
  return tools.map((tool) => ({
    ...tool,
    is_local: tool.source === "local",
  }));
}

export async function callTool(
  toolName: string,
  argumentsPayload: Record<string, unknown>,
): Promise<ToolCallResult> {
  return apiFetch<ToolCallResult>(`/tools/${encodeURIComponent(toolName)}/call`, {
    method: "POST",
    body: JSON.stringify({ arguments: argumentsPayload }),
  });
}
