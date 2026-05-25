import Link from "next/link";
import { listTasks } from "@/lib/api/tasks";
import type { TaskItem } from "@/types/api";
import { formatDateTime, statusClass, statusLabel } from "@/lib/status";

type TasksPageProps = {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export default async function TasksPage({ searchParams }: TasksPageProps) {
  const params = (await searchParams) ?? {};
  let errorText = "";
  if (typeof params.error === "string") {
    try {
      errorText = decodeURIComponent(params.error);
    } catch {
      errorText = params.error;
    }
  }

  let tasksError = "";
  let tasks: TaskItem[] = [];
  try {
    tasks = await listTasks(30);
  } catch (error) {
    tasksError = error instanceof Error ? error.message : "任务列表加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">任务中心</h1>
        <p className="page-subtitle">
          支持离线模式下的任务创建、任务追踪与状态查看，面向日常运营重复操作。
        </p>
      </header>

      <section className="section card">
        <div className="toolbar" style={{ justifyContent: "space-between" }}>
          <div className="muted">建议先创建任务，再在此列表追踪执行状态与结果。</div>
          <Link className="button" href="/tasks/create">
            新建任务
          </Link>
        </div>
      </section>

      {errorText ? <div className="card">任务创建失败：{errorText}</div> : null}

      <section className="section card">
        <h2 className="card-title">任务列表</h2>
        {tasksError ? (
          <div className="empty">任务列表加载失败：{tasksError}</div>
        ) : tasks.length === 0 ? (
          <div className="empty">暂无任务，可先创建一个离线任务进行验证。</div>
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
                {tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td className="mono">
                      <Link href={`/tasks/${task.task_id}`}>{task.task_id}</Link>
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
    </div>
  );
}
