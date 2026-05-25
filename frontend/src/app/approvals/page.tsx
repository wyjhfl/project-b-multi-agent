import Link from "next/link";
import { getApprovalSummary, listApprovals } from "@/lib/api/approvals";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";
import type { ApprovalItem, ApprovalSummary } from "@/types/api";

type ApprovalsPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

const statusOptions = [
  { value: "pending", label: "待审批" },
  { value: "approved", label: "已通过" },
  { value: "rejected", label: "已拒绝" },
  { value: "all", label: "全部" },
] as const;

function getStatusValue(raw: string | string[] | undefined): string {
  if (Array.isArray(raw)) {
    return raw[0] || "pending";
  }
  if (!raw) {
    return "pending";
  }
  return statusOptions.some((item) => item.value === raw) ? raw : "pending";
}

function extractCreatedAt(item: ApprovalItem): string {
  return item.requested_at || item.created_at || "";
}

export default async function ApprovalsPage({ searchParams }: ApprovalsPageProps) {
  const params = (await searchParams) ?? {};
  const activeStatus = getStatusValue(params.status);

  let summaryError = "";
  let listError = "";
  let summary: ApprovalSummary | null = null;
  let approvals: ApprovalItem[] = [];

  try {
    summary = await getApprovalSummary();
  } catch (error) {
    summaryError = error instanceof Error ? error.message : "审批概览加载失败";
  }

  try {
    approvals = await listApprovals(activeStatus, 50);
  } catch (error) {
    listError = error instanceof Error ? error.message : "审批列表加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">审批中心</h1>
        <p className="page-subtitle">查看审批队列与历史决策，并进入详情页执行审批动作。</p>
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
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <h2 className="card-title" style={{ marginBottom: 0 }}>
            审批列表
          </h2>
          <div className="toolbar">
            {statusOptions.map((option) => (
              <Link
                key={option.value}
                href={`/approvals?status=${option.value}`}
                className={`button ${activeStatus === option.value ? "" : "secondary"}`}
              >
                {option.label}
              </Link>
            ))}
          </div>
        </div>

        {listError ? (
          <div className="empty">审批列表加载失败：{listError}</div>
        ) : approvals.length === 0 ? (
          <div className="empty">当前筛选条件下没有审批项。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>审批 ID</th>
                  <th>任务 ID</th>
                  <th>工具 / 动作</th>
                  <th>风险等级</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {approvals.map((item) => (
                  <tr key={item.approval_id}>
                    <td className="mono">{item.approval_id}</td>
                    <td className="mono">
                      <Link href={`/tasks/${item.task_id}`}>{item.task_id}</Link>
                    </td>
                    <td>
                      <div>{item.tool_name || "-"}</div>
                      <div className="muted">{item.action || "-"}</div>
                    </td>
                    <td>{item.risk_level || "-"}</td>
                    <td>
                      <span className={`badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
                    </td>
                    <td>{formatDateTime(extractCreatedAt(item))}</td>
                    <td>
                      <Link className="button secondary" href={`/approvals/${item.approval_id}`}>
                        查看详情
                      </Link>
                    </td>
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
