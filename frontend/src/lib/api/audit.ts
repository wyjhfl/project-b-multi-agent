import { apiFetch } from "@/lib/api/client";
import type { AuditEvent, AuditFilters } from "@/types/api";

export async function listAuditEvents(filters: AuditFilters = {}): Promise<AuditEvent[]> {
  const query = new URLSearchParams();
  if (filters.event_type) {
    query.set("event_type", filters.event_type);
  }
  if (filters.actor) {
    query.set("actor", filters.actor);
  }
  if (filters.task_id) {
    query.set("task_id", filters.task_id);
  }
  if (filters.approval_id) {
    query.set("approval_id", filters.approval_id);
  }
  if (filters.outcome) {
    query.set("outcome", filters.outcome);
  }
  if (filters.severity) {
    query.set("severity", filters.severity);
  }
  if (filters.start_time) {
    query.set("start_time", filters.start_time);
  }
  if (filters.end_time) {
    query.set("end_time", filters.end_time);
  }
  query.set("limit", String(filters.limit ?? 100));
  return apiFetch<AuditEvent[]>(`/audit/events?${query.toString()}`);
}

export async function getAuditEvent(eventId: string): Promise<AuditEvent> {
  return apiFetch<AuditEvent>(`/audit/events/${eventId}`);
}
