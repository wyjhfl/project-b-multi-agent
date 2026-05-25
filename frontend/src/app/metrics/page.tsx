import {
  getCostSummary,
  getRuntimeSummary,
  getTasksSummary,
  getToolsSummary,
} from "@/lib/api/metrics";
import type { CostSummary, RuntimeSummary, TasksSummary, ToolsSummary } from "@/types/api";

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

function percent(value: number, total: number): string {
  if (!total) {
    return "0.00%";
  }
  return `${((value / total) * 100).toFixed(2)}%`;
}

function topTools(tools: ToolsSummary | null): Array<{ name: string; callCount: number; failureCount: number }> {
  const byTool = tools?.by_tool || {};
  return Object.entries(byTool)
    .map(([name, item]) => ({
      name,
      callCount: item.call_count || 0,
      failureCount: item.failure_count || 0,
    }))
    .sort((a, b) => b.callCount - a.callCount)
    .slice(0, 8);
}

export default async function MetricsPage() {
  const [runtimeRes, tasksRes, toolsRes, costRes] = await Promise.all([
    safeLoad(() => getRuntimeSummary()),
    safeLoad(() => getTasksSummary()),
    safeLoad(() => getToolsSummary()),
    safeLoad(() => getCostSummary()),
  ]);

  const runtime: RuntimeSummary | null = runtimeRes.data;
  const tasks: TasksSummary | null = tasksRes.data;
  const tools: ToolsSummary | null = toolsRes.data;
  const cost: CostSummary | null = costRes.data;
  const toolFailureRate = percent(tools?.tool_failure_count || 0, tools?.tool_call_count || 0);
  const topToolList = topTools(tools);

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">指标中心</h1>
        <p className="page-subtitle">聚合展示 Runtime / Tasks / Tools / Cost 指标，不做复杂 BI 图表。</p>
      </header>

      <section className="section card">
        <h2 className="card-title">Runtime Summary</h2>
        {runtimeRes.error ? (
          <div className="empty">加载失败：{runtimeRes.error}</div>
        ) : (
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">任务总数</div>
              <div className="metric-value">{runtime?.task_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">成功任务</div>
              <div className="metric-value">{runtime?.success_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">失败任务</div>
              <div className="metric-value">{runtime?.failed_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">待审批任务</div>
              <div className="metric-value">{runtime?.waiting_approval_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">工具调用数</div>
              <div className="metric-value">{runtime?.tool_call_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">累计成本</div>
              <div className="metric-value">{runtime?.total_cost?.toFixed?.(4) ?? "-"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">Tasks Summary</h2>
        {tasksRes.error ? (
          <div className="empty">加载失败：{tasksRes.error}</div>
        ) : (
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">总数</div>
              <div className="metric-value">{tasks?.task_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">成功</div>
              <div className="metric-value">{tasks?.success_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">失败</div>
              <div className="metric-value">{tasks?.failed_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">待审批</div>
              <div className="metric-value">{tasks?.waiting_approval_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">取消</div>
              <div className="metric-value">{tasks?.cancelled_count ?? "-"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">平均耗时(ms)</div>
              <div className="metric-value">{tasks?.avg_task_latency_ms?.toFixed?.(1) ?? "-"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">Tools Summary</h2>
        {toolsRes.error ? (
          <div className="empty">加载失败：{toolsRes.error}</div>
        ) : (
          <div className="stack">
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">调用数</div>
                <div className="metric-value">{tools?.tool_call_count ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">失败数</div>
                <div className="metric-value">{tools?.tool_failure_count ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">失败率</div>
                <div className="metric-value">{toolFailureRate}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">重试次数</div>
                <div className="metric-value">{tools?.retry_count ?? "-"}</div>
              </div>
            </div>

            {topToolList.length > 0 ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Top Tool</th>
                      <th>调用数</th>
                      <th>失败数</th>
                    </tr>
                  </thead>
                  <tbody>
                    {topToolList.map((item) => (
                      <tr key={item.name}>
                        <td className="mono">{item.name}</td>
                        <td>{item.callCount}</td>
                        <td>{item.failureCount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty">暂无工具统计数据。</div>
            )}
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">Cost Summary</h2>
        {costRes.error ? (
          <div className="empty">加载失败：{costRes.error}</div>
        ) : (
          <div className="stack">
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">prompt_tokens</div>
                <div className="metric-value">{cost?.total_prompt_tokens ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">completion_tokens</div>
                <div className="metric-value">{cost?.total_completion_tokens ?? "-"}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">cost</div>
                <div className="metric-value">{cost?.total_cost?.toFixed?.(4) ?? "-"}</div>
              </div>
            </div>
            <div>
              <div className="label">by_mode</div>
              <pre className="json-box">{JSON.stringify(cost?.by_mode ?? {}, null, 2)}</pre>
            </div>
            <div>
              <div className="label">by_day</div>
              <pre className="json-box">{JSON.stringify(cost?.by_day ?? {}, null, 2)}</pre>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">LLM 预算与缓存摘要</h2>
        {runtimeRes.error ? (
          <div className="empty">加载失败：{runtimeRes.error}</div>
        ) : (
          <div className="form-grid">
            <div>
              <div className="label">llm_budget</div>
              <pre className="json-box">{JSON.stringify(runtime?.llm_budget ?? {}, null, 2)}</pre>
            </div>
            <div>
              <div className="label">llm_cache</div>
              <pre className="json-box">{JSON.stringify(runtime?.llm_cache ?? {}, null, 2)}</pre>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
