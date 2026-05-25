export function statusClass(status: string): string {
  switch (status) {
    case "completed":
    case "approved":
      return "status-completed";
    case "failed":
    case "rejected":
      return "status-failed";
    case "waiting_approval":
    case "pending":
      return "status-waiting_approval";
    case "cancelled":
      return "status-cancelled";
    case "running":
    case "created":
      return "status-running";
    default:
      return "status-default";
  }
}

export function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    case "waiting_approval":
      return "待审批";
    case "cancelled":
      return "已取消";
    case "running":
      return "运行中";
    case "created":
      return "已创建";
    case "pending":
      return "待处理";
    case "approved":
      return "已通过";
    case "rejected":
      return "已拒绝";
    default:
      return status || "未知";
  }
}

export function formatDateTime(value?: string): string {
  if (!value) {
    return "-";
  }
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return value;
  }
  return d.toLocaleString("zh-CN", { hour12: false });
}
