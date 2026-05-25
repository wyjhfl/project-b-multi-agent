import Link from "next/link";
import { getTask, getTaskTrace } from "@/lib/api/tasks";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";
import type { TaskItem, TraceEvent } from "@/types/api";

type TaskDetailPageProps = {
  params: Promise<{ taskId: string }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

function renderJson(value: unknown) {
  if (value == null) {
    return <div className="empty">无</div>;
  }
  return <pre className="json-box">{JSON.stringify(value, null, 2)}</pre>;
}

function renderCompactJson(value: unknown) {
  if (value == null) {
    return "-";
  }
  const text = JSON.stringify(value);
  if (!text) {
    return "-";
  }
  if (text.length <= 120) {
    return text;
  }
  return `${text.slice(0, 120)}...`;
}

export default async function TaskDetailPage({ params, searchParams }: TaskDetailPageProps) {
  const { taskId } = await params;
  const query = (await searchParams) ?? {};
  const created = query.created === "1";

  let task: TaskItem | null = null;
  let taskError = "";
  try {
    task = await getTask(taskId);
    if ((task as unknown as { error?: string }).error) {
      taskError = String((task as unknown as { error?: string }).error);
      task = null;
    }
  } catch (error) {
    taskError = error instanceof Error ? error.message : "任务详情加载失败";
  }

  let traceEvents: TraceEvent[] = [];
  let traceError = "";
  try {
    const trace = await getTaskTrace(taskId);
    traceEvents = trace.events ?? [];
  } catch (error) {
    traceError = error instanceof Error ? error.message : "Trace 加载失败";
  }

  return (
    <div className="stack">
      <header className="toolbar" style={{ justifyContent: "space-between" }}>
        <div>
          <h1 className="page-title">任务详情</h1>
          <p className="page-subtitle">查看任务结果、错误原因与执行时间线。</p>
        </div>
        <Link className="button secondary" href="/tasks">
          返回任务列表
        </Link>
      </header>

      {created ? <div className="card">任务已创建，正在展示最新详情。</div> : null}

      <section className="section card">
        <h2 className="card-title">基本信息</h2>
        {taskError ? (
          <div className="empty">任务加载失败：{taskError}</div>
        ) : !task ? (
          <div className="empty">任务不存在。</div>
        ) : (
          <div className="stack">
            <div>
              <div className="label">任务 ID</div>
              <div className="mono">{task.task_id}</div>
            </div>
            <div>
              <div className="label">查询</div>
              <div>{task.query}</div>
            </div>
            <div className="toolbar">
              <div>
                <div className="label">模式</div>
                <div>{task.mode || "-"}</div>
              </div>
              <div>
                <div className="label">状态</div>
                <span className={`badge ${statusClass(task.status)}`}>
                  {statusLabel(task.status)}
                </span>
              </div>
              <div>
                <div className="label">创建时间</div>
                <div>{formatDateTime(task.created_at)}</div>
              </div>
              <div>
                <div className="label">更新时间</div>
                <div>{formatDateTime(task.updated_at)}</div>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">执行结果（result）</h2>
        {task ? renderJson(task.result) : <div className="empty">无可展示结果。</div>}
      </section>

      <section className="section card">
        <h2 className="card-title">错误信息（error）</h2>
        {task?.error ? renderJson(task.error) : <div className="empty">无错误信息。</div>}
      </section>

      <section className="section card">
        <h2 className="card-title">Trace 时间线</h2>
        {traceError ? (
          <div className="empty">Trace 加载失败：{traceError}</div>
        ) : traceEvents.length === 0 ? (
          <div className="empty">暂无 Trace 事件。</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>事件类型</th>
                  <th>执行者</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                {traceEvents.map((event) => (
                  <tr key={event.event_id || `${event.timestamp}-${event.event_type}`}>
                    <td>{formatDateTime(event.timestamp)}</td>
                    <td className="mono">{event.event_type}</td>
                    <td>{event.actor || "-"}</td>
                    <td className="mono">{renderCompactJson(event.detail)}</td>
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
