import Link from "next/link";
import { getApproval, getApprovalContext } from "@/lib/api/approvals";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";
import type { ApprovalContext, ApprovalItem } from "@/types/api";
import ApprovalActions from "./ApprovalActions";

type ApprovalDetailPageProps = {
  params: Promise<{ approvalId: string }>;
};

function renderJson(value: unknown) {
  if (value == null) {
    return <div className="empty">无</div>;
  }
  return <pre className="json-box">{JSON.stringify(value, null, 2)}</pre>;
}

function getCreatedAt(approval?: ApprovalItem): string {
  if (!approval) {
    return "";
  }
  return approval.requested_at || approval.created_at || "";
}

function getErrorFromContext(context: ApprovalContext | null): string {
  if (!context) {
    return "";
  }
  return context.error || "";
}

export default async function ApprovalDetailPage({ params }: ApprovalDetailPageProps) {
  const { approvalId } = await params;

  let approval: ApprovalItem | null = null;
  let approvalError = "";
  try {
    approval = await getApproval(approvalId);
    if (approval.error) {
      approvalError = approval.error;
      approval = null;
    }
  } catch (error) {
    approvalError = error instanceof Error ? error.message : "审批详情加载失败";
  }

  let context: ApprovalContext | null = null;
  let contextError = "";
  try {
    context = await getApprovalContext(approvalId);
    const apiError = getErrorFromContext(context);
    if (apiError) {
      contextError = apiError;
      context = null;
    }
  } catch (error) {
    contextError = error instanceof Error ? error.message : "审批上下文加载失败";
  }

  const mergedApproval = context?.approval || approval;
  const relatedTaskId = mergedApproval?.task_id || "";

  return (
    <div className="stack">
      <header className="toolbar" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">审批详情</h1>
          <p className="page-subtitle">查看审批上下文并执行通过、拒绝、恢复动作。</p>
        </div>
        <div className="toolbar">
          <Link className="button secondary" href="/approvals">
            返回审批中心
          </Link>
          {relatedTaskId ? (
            <Link className="button secondary" href={`/tasks/${relatedTaskId}`}>
              查看关联任务
            </Link>
          ) : null}
        </div>
      </header>

      {relatedTaskId ? (
        <section className="section card">
          <div className="toolbar" style={{ justifyContent: "space-between" }}>
            <h2 className="card-title" style={{ marginBottom: 0 }}>
              可观测入口
            </h2>
            <div className="toolbar">
              <Link className="button secondary" href={`/observability?task_id=${relatedTaskId}`}>
                查看关联 Trace
              </Link>
              <Link className="button secondary" href={`/audit?task_id=${relatedTaskId}`}>
                查看关联 Audit
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      <section className="section card">
        <h2 className="card-title">审批基本信息</h2>
        {approvalError ? (
          <div className="empty">审批详情加载失败：{approvalError}</div>
        ) : !mergedApproval ? (
          <div className="empty">审批不存在。</div>
        ) : (
          <div className="stack">
            <div>
              <div className="label">审批 ID</div>
              <div className="mono">{mergedApproval.approval_id}</div>
            </div>
            <div className="toolbar">
              <div>
                <div className="label">任务 ID</div>
                <div className="mono">{mergedApproval.task_id || "-"}</div>
              </div>
              <div>
                <div className="label">工具名称</div>
                <div>{mergedApproval.tool_name || "-"}</div>
              </div>
              <div>
                <div className="label">动作</div>
                <div>{mergedApproval.action || "-"}</div>
              </div>
              <div>
                <div className="label">风险等级</div>
                <div>{mergedApproval.risk_level || "-"}</div>
              </div>
              <div>
                <div className="label">状态</div>
                <span className={`badge ${statusClass(mergedApproval.status)}`}>
                  {statusLabel(mergedApproval.status)}
                </span>
              </div>
            </div>
            <div className="toolbar">
              <div>
                <div className="label">创建时间</div>
                <div>{formatDateTime(getCreatedAt(mergedApproval))}</div>
              </div>
              <div>
                <div className="label">决策时间</div>
                <div>{formatDateTime(mergedApproval.decided_at || "")}</div>
              </div>
              <div>
                <div className="label">决策人</div>
                <div>{mergedApproval.decided_by || "-"}</div>
              </div>
              <div>
                <div className="label">决策原因</div>
                <div>{mergedApproval.decision_reason || "-"}</div>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">审批动作</h2>
        {mergedApproval ? (
          <ApprovalActions
            approvalId={mergedApproval.approval_id}
            canApprove={context?.can_approve ?? mergedApproval.status === "pending"}
            canReject={context?.can_reject ?? mergedApproval.status === "pending"}
            canResume={context?.can_resume ?? false}
          />
        ) : (
          <div className="empty">审批不存在，无法执行动作。</div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">上下文摘要</h2>
        {contextError ? (
          <div className="empty">审批上下文加载失败：{contextError}</div>
        ) : !context ? (
          <div className="empty">暂无上下文信息。</div>
        ) : (
          <div className="stack">
            <div className="toolbar">
              <div>
                <div className="label">可通过</div>
                <div>{context.can_approve ? "是" : "否"}</div>
              </div>
              <div>
                <div className="label">可拒绝</div>
                <div>{context.can_reject ? "是" : "否"}</div>
              </div>
              <div>
                <div className="label">可恢复</div>
                <div>{context.can_resume ? "是" : "否"}</div>
              </div>
              <div>
                <div className="label">恢复状态</div>
                <div>{context.resume_status || "-"}</div>
              </div>
            </div>
            <div>
              <div className="label">审批 payload</div>
              {renderJson(context.payload)}
            </div>
            <div>
              <div className="label">关联任务信息</div>
              {context.task ? (
                <div className="stack">
                  <div className="mono">{context.task.task_id}</div>
                  <div>{context.task.query}</div>
                  <div>
                    <span className={`badge ${statusClass(context.task.status)}`}>
                      {statusLabel(context.task.status)}
                    </span>
                  </div>
                </div>
              ) : (
                <div className="empty">未找到关联任务。</div>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">审批时间线</h2>
        {!context || context.timeline.length === 0 ? (
          <div className="empty">暂无审批相关时间线。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>事件类型</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                {context.timeline.map((item, index) => (
                  <tr key={`${item.timestamp}-${item.event_type}-${index}`}>
                    <td>{formatDateTime(item.timestamp)}</td>
                    <td className="mono">{item.event_type}</td>
                    <td className="mono">{JSON.stringify(item.detail ?? {})}</td>
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
