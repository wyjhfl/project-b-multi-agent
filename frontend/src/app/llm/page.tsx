import { getLlmPreflight } from "@/lib/api/llm";

function boolLabel(value: boolean): string {
  return value ? "true" : "false";
}

export default async function LlmPilotPage() {
  let preflight = null;
  let errorText = "";

  try {
    preflight = await getLlmPreflight(false);
  } catch (error) {
    errorText = error instanceof Error ? error.message : "预检状态加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">LLM Controlled Pilot</h1>
        <p className="page-subtitle">
          本页仅展示真实 LLM 受控试点的配置与预检状态。默认 fake/offline，默认不联网。
        </p>
      </header>

      <section className="section card">
        <h2 className="card-title">试点边界</h2>
        <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
          <li>默认不启用真实 LLM，不进入默认 pytest/CI。</li>
          <li>不提供 API key 输入，不展示密钥原文。</li>
          <li>network_check 只有显式开关开启且配置完整时才允许执行。</li>
        </ul>
      </section>

      <section className="section card">
        <h2 className="card-title">Preflight 状态</h2>
        {errorText ? (
          <div className="empty">{errorText}</div>
        ) : !preflight ? (
          <div className="empty">暂无数据</div>
        ) : (
          <div className="stack">
            <div className="metric-grid">
              <div className="metric-card">
                <div className="metric-label">status</div>
                <div className="metric-value">{preflight.status}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">allowed</div>
                <div className="metric-value">{boolLabel(preflight.allowed)}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">network_check_allowed</div>
                <div className="metric-value">{boolLabel(preflight.network_check_allowed)}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">api_key_present</div>
                <div className="metric-value">{boolLabel(preflight.api_key_present)}</div>
              </div>
            </div>

            <div className="form-grid">
              <div>
                <div className="label">provider</div>
                <div className="mono">{preflight.provider || "<empty>"}</div>
              </div>
              <div>
                <div className="label">model</div>
                <div className="mono">{preflight.model || "<empty>"}</div>
              </div>
              <div>
                <div className="label">base_url（已脱敏）</div>
                <div className="mono">{preflight.base_url || "<empty>"}</div>
              </div>
              <div>
                <div className="label">api_key_env</div>
                <div className="mono">{preflight.api_key_env || "<empty>"}</div>
              </div>
            </div>

            <div>
              <div className="label">errors</div>
              {preflight.errors.length === 0 ? (
                <div className="empty">无</div>
              ) : (
                <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
                  {preflight.errors.map((item: string) => (
                    <li key={item} className="mono">{item}</li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <div className="label">warnings</div>
              {preflight.warnings.length === 0 ? (
                <div className="empty">无</div>
              ) : (
                <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
                  {preflight.warnings.map((item: string) => (
                    <li key={item} className="mono">{item}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
