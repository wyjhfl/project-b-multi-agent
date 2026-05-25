"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div className="stack">
      <h2 className="page-title">页面加载失败</h2>
      <p className="muted">错误信息：{error.message}</p>
      <button className="button" onClick={() => reset()}>
        重试
      </button>
    </div>
  );
}
