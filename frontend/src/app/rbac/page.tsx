import { getHealthStatus } from "@/lib/api/system";

export default async function RbacPage() {
  let errorText = "";
  let authEnabled = false;
  let rbacEnabled: boolean | null = null;

  try {
    const health = await getHealthStatus();
    authEnabled = Boolean(health.auth_enabled);
    rbacEnabled = typeof health.rbac_enabled === "boolean" ? health.rbac_enabled : null;
  } catch (error) {
    errorText = error instanceof Error ? error.message : "状态加载失败";
  }

  return (
    <div className="stack">
      <header>
        <h1 className="page-title">权限说明（RBAC 试点）</h1>
        <p className="page-subtitle">用于演示模式与启用权限模式的边界说明，不包含生产登录系统。</p>
      </header>

      <section className="section card">
        <h2 className="card-title">当前运行模式</h2>
        {errorText ? (
          <div className="empty">状态加载失败：{errorText}</div>
        ) : (
          <div className="metric-grid">
            <div className="metric-card">
              <div className="metric-label">AUTH_ENABLED</div>
              <div className="metric-value">{authEnabled ? "true" : "false"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">RBAC_ENABLED</div>
              <div className="metric-value">{rbacEnabled == null ? "未上报" : rbacEnabled ? "true" : "false"}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">默认演示路径</div>
              <div className="metric-value">{!authEnabled && (rbacEnabled == null || !rbacEnabled) ? "已开启" : "已关闭"}</div>
            </div>
          </div>
        )}
      </section>

      <section className="section card">
        <h2 className="card-title">试点角色边界</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>角色</th>
                <th>定位</th>
                <th>典型权限</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="mono">admin</td>
                <td>全局管理</td>
                <td>任务、审批、审计、指标全量访问</td>
              </tr>
              <tr>
                <td className="mono">operator</td>
                <td>运营执行</td>
                <td>创建任务、审批通过/拒绝/恢复、查看指标</td>
              </tr>
              <tr>
                <td className="mono">viewer</td>
                <td>只读观察</td>
                <td>查看任务/审批/指标，不执行高风险动作</td>
              </tr>
              <tr>
                <td className="mono">auditor</td>
                <td>合规审计</td>
                <td>重点查看审计与追踪，可读指标</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section className="section card">
        <h2 className="card-title">启用方式（试点）</h2>
        <ul className="stack" style={{ margin: 0, paddingLeft: 18 }}>
          <li>默认配置为 AUTH/RBAC 关闭，便于离线演示。</li>
          <li>如需启用权限控制，请设置环境变量：`AUTH_ENABLED=true` 与 `RBAC_ENABLED=true`。</li>
          <li>当前不实现生产登录系统，不提供 SSO、多租户能力。</li>
        </ul>
      </section>
    </div>
  );
}
