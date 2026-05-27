import Link from "next/link";
import { getApprovalSummary, listPendingApprovals } from "@/lib/api/approvals";
import { getRuntimeSummary, getTasksSummary } from "@/lib/api/metrics";
import { listTasks } from "@/lib/api/tasks";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";

type SafeResult<T> = {
  data: T | null;
  error: string | null;
};

async function safeLoad<T>(loader: () => Promise<T>): Promise<SafeResult<T>> {
  try {
    return { data: await loader(), error: null };
  } catch (error) {
    return {
      data: null,
      error: error instanceof Error ? error.message : "未知错误",
    };
  }
}

export default async function DashboardPage() {
  const [runtimeRes, taskSummaryRes, approvalSummaryRes, tasksRes, pendingRes] =
    await Promise.all([
      safeLoad(() => getRuntimeSummary()),
      safeLoad(() => getTasksSummary()),
      safeLoad(() => getApprovalSummary()),
      safeLoad(() => listTasks(8)),
      safeLoad(() => listPendingApprovals(8)),
    ]);

  const runtime = runtimeRes.data;
  const taskSummary = taskSummaryRes.data;
  const approvalSummary = approvalSummaryRes.data;
  const recentTasks = tasksRes.data ?? [];
  const pendingApprovals = pendingRes.data ?? [];

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">聚焦任务执行、审批积压与运行状态，支持日常运营巡检与问题定位。</p>
      </header>

      <section className="section">
        <div className="metric-grid">
          <div className="metric-card">
            <div className="metric-label">任务总数</div>
            <div className="metric-value">{taskSummary?.task_count ?? "-"}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">待审批任务</div>
            <div className="metric-value">{approvalSummary?.pending_count ?? "-"}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">失败任务</div>
            <div className="metric-value">{taskSummary?.failed_count ?? "-"}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">工具失败次数</div>
            <div className="metric-value">{runtime?.tool_failure_count ?? "-"}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">LLM 累计成本</div>
            <div className="metric-value">{runtime?.total_cost?.toFixed?.(4) ?? "-"}</div>
          </div>
          <div className="metric-card">
            <div className="metric-label">运行中 / 待审批</div>
            <div className="metric-value">{runtime?.waiting_approval_count ?? "-"}</div>
          </div>
        </div>
      </section>

      <section className="section card">
        <h2 className="card-title">快速入口</h2>
        <div className="toolbar">
          <Link className="button" href="/tasks">
            任务中心
          </Link>
          <Link className="button secondary" href="/approvals">
            审批中心
          </Link>
          <Link className="button secondary" href="/observability">
            追踪审计
          </Link>
          <Link className="button secondary" href="/metrics">
            指标中心
          </Link>
          <Link className="button secondary" href="/tools">
            工具目录
          </Link>
          <Link className="button secondary" href="/nl2sql">
            NL2SQL
          </Link>
          <Link className="button secondary" href="/llm">
            LLM Pilot
          </Link>
        </div>
      </section>

      <section className="section card">
        <h2 className="card-title">最近任务</h2>
        {tasksRes.error ? (
          <div className="empty">任务加载失败：{tasksRes.error}</div>
        ) : recentTasks.length === 0 ? (
          <div className="empty">暂无任务，请先在任务中心创建。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>任务 ID</th>
                  <th>查询</th>
                  <th>模式</th>
                  <th>状态</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                {recentTasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="mono">
                      <Link href={`/tasks/${task.task_id}`}>{task.task_id.slice(0, 10)}...</Link>
                    </td>
                    <td>{task.query}</td>
                    <td>{task.mode || "-"}</td>
                    <td>
                      <span className={`badge ${statusClass(task.status)}`}>
                        {statusLabel(task.status)}
                      </span>
                    </td>
                    <td>{formatDateTime(task.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">待审批列表</h2>
        {pendingRes.error ? (
          <div className="empty">审批数据加载失败：{pendingRes.error}</div>
        ) : pendingApprovals.length === 0 ? (
          <div className="empty">当前无待审批项。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>审批 ID</th>
                  <th>任务 ID</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {pendingApprovals.map((item) => (
                  <tr key={item.approval_id}>
                    <td className="mono">{item.approval_id.slice(0, 12)}...</td>
                    <td className="mono">{item.task_id.slice(0, 12)}...</td>
                    <td>
                      <span className={`badge ${statusClass(item.status)}`}>
                        {statusLabel(item.status)}
                      </span>
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
