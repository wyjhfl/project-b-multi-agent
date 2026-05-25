import Link from "next/link";
import { getApprovalSummary, listPendingApprovals } from "@/lib/api/approvals";
import type { ApprovalSummary } from "@/types/api";
import type { ApprovalItem } from "@/lib/api/approvals";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";

export default async function ApprovalsPage() {
  let summaryError = "";
  let pendingError = "";
  let summary: ApprovalSummary | null = null;
  let pendingList: ApprovalItem[] = [];

  try {
    summary = await getApprovalSummary();
  } catch (error) {
    summaryError = error instanceof Error ? error.message : "审批概览加载失败";
  }

  try {
    pendingList = await listPendingApprovals(20);
  } catch (error) {
    pendingError = error instanceof Error ? error.message : "待审批列表加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">审批入口（轻量）</h1>
        <p className="page-subtitle">
          当前仅提供待审批可视化入口，不在 v2.4.1 实现完整 approve/reject/resume 动作页。
        </p>
      </header>

      <section className="section card">
        <h2 className="card-title">审批概览</h2>
        {summaryError ? (
          <div className="empty">审批概览加载失败：{summaryError}</div>
        ) : (
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">待审批</div>
              <div className="metric-value">{summary?.pending_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">已通过</div>
              <div className="metric-value">{summary?.approved_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">已拒绝</div>
              <div className="metric-value">{summary?.rejected_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">已过期</div>
              <div className="metric-value">{summary?.expired_count ?? "-"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">待审批列表</h2>
        {pendingError ? (
          <div className="empty">待审批列表加载失败：{pendingError}</div>
        ) : pendingList.length === 0 ? (
          <div className="empty">当前没有待审批项。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>审批 ID</th>
                  <th>任务 ID</th>
                  <th>状态</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                {pendingList.map((item) => (
                  <tr key={item.approval_id}>
                    <td className="mono">{item.approval_id}</td>
                    <td className="mono">
                      <Link href={`/tasks/${item.task_id}`}>{item.task_id}</Link>
                    </td>
                    <td>
                      <span className={`badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td>{formatDateTime(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
