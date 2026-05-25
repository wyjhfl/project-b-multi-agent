import Link from "next/link";
import { getAuditEvent } from "@/lib/api/audit";
import { formatDateTime } from "@/lib/status";
import type { AuditEvent } from "@/types/api";

type AuditDetailPageProps = {
  params: Promise<{ eventId: string }>;
};

export default async function AuditDetailPage({ params }: AuditDetailPageProps) {
  const { eventId } = await params;

  let event: AuditEvent | null = null;
  let errorText = "";
  try {
    event = await getAuditEvent(eventId);
    if (event.error) {
      errorText = event.error;
      event = null;
    }
  } catch (error) {
    errorText = error instanceof Error ? error.message : "审计详情加载失败";
  }

  return (
    <div className="stack">
      <header className="toolbar" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">审计详情</h1>
          <p className="page-subtitle">查看单条审计事件的完整字段与 detail JSON。</p>
        </div>
        <Link className="button secondary" href="/audit">
          返回审计列表
        </Link>
      </header>

      <section className="section card">
        <h2 className="card-title">基础信息</h2>
        {errorText ? (
          <div className="empty">审计详情加载失败：{errorText}</div>
        ) : !event ? (
          <div className="empty">审计事件不存在。</div>
        ) : (
          <div className="stack">
            <div>
              <div className="label">event_id</div>
              <div className="mono">{event.event_id}</div>
            </div>
            <div className="toolbar">
              <div>
                <div className="label">event_type</div>
                <div className="mono">{event.event_type}</div>
              </div>
              <div>
                <div className="label">actor</div>
                <div>{event.actor || "-"}</div>
              </div>
              <div>
                <div className="label">task_id</div>
                <div className="mono">{event.task_id || "-"}</div>
              </div>
              <div>
                <div className="label">approval_id</div>
                <div className="mono">{event.approval_id || "-"}</div>
              </div>
            </div>
            <div className="toolbar">
              <div>
                <div className="label">action</div>
                <div>{event.action || "-"}</div>
              </div>
              <div>
                <div className="label">outcome</div>
                <div>{event.outcome || "-"}</div>
              </div>
              <div>
                <div className="label">severity</div>
                <div>{event.severity || "-"}</div>
              </div>
              <div>
                <div className="label">timestamp</div>
                <div>{formatDateTime(event.timestamp)}</div>
              </div>
            </div>
            <div>
              <div className="label">reason</div>
              <div>{event.reason || "-"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">detail JSON</h2>
        {!event ? (
          <div className="empty">无可展示内容。</div>
        ) : (
          <pre className="json-box">{JSON.stringify(event.detail ?? {}, null, 2)}</pre>
        )}
      </section>
    </div>
  );
}
