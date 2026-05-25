"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  approveApproval,
  rejectApproval,
  resumeApproval,
} from "@/lib/api/approvals";

type ApprovalActionsProps = {
  approvalId: string;
  canApprove: boolean;
  canReject: boolean;
  canResume: boolean;
};

export default function ApprovalActions({
  approvalId,
  canApprove,
  canReject,
  canResume,
}: ApprovalActionsProps) {
  const router = useRouter();
  const [decidedBy, setDecidedBy] = useState("operator");
  const [reason, setReason] = useState("");
  const [autoResume, setAutoResume] = useState(true);
  const [loadingAction, setLoadingAction] = useState<"" | "approve" | "reject" | "resume">("");
  const [resultMessage, setResultMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const disabled = useMemo(() => loadingAction !== "", [loadingAction]);

  async function handleApprove() {
    setLoadingAction("approve");
    setResultMessage("");
    setErrorMessage("");
    try {
      const result = await approveApproval(approvalId, {
        decided_by: decidedBy.trim() || "operator",
        reason: reason.trim(),
        auto_resume: autoResume,
      });
      if (result.error) {
        setErrorMessage(result.error);
      } else if (result.already_resumed) {
        setResultMessage("审批已恢复执行，无需重复操作。");
      } else if (result.already_decided) {
        setResultMessage("审批已决策，本次未重复提交。");
      } else {
        setResultMessage("审批通过已提交。");
      }
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "审批通过失败");
    } finally {
      setLoadingAction("");
    }
  }

  async function handleReject() {
    setLoadingAction("reject");
    setResultMessage("");
    setErrorMessage("");
    try {
      const result = await rejectApproval(approvalId, {
        decided_by: decidedBy.trim() || "operator",
        reason: reason.trim(),
      });
      if (result.error) {
        setErrorMessage(result.error);
      } else if (result.already_decided) {
        setResultMessage("审批已决策，本次未重复提交。");
      } else {
        setResultMessage("审批拒绝已提交。");
      }
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "审批拒绝失败");
    } finally {
      setLoadingAction("");
    }
  }

  async function handleResume() {
    setLoadingAction("resume");
    setResultMessage("");
    setErrorMessage("");
    try {
      const result = await resumeApproval(approvalId);
      if (result.error) {
        setErrorMessage(result.error);
      } else if (result.already_resumed) {
        setResultMessage("审批已恢复执行，无需重复操作。");
      } else {
        setResultMessage("手动恢复已提交。");
      }
      router.refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "手动恢复失败");
    } finally {
      setLoadingAction("");
    }
  }

  return (
    <div className="stack">
      <div className="form-grid">
        <div>
          <label className="label" htmlFor="decided_by">
            操作人
          </label>
          <input
            id="decided_by"
            className="input"
            value={decidedBy}
            onChange={(event) => setDecidedBy(event.target.value)}
            placeholder="operator"
            disabled={disabled}
          />
        </div>
        <div>
          <label className="label" htmlFor="reason">
            原因说明
          </label>
          <input
            id="reason"
            className="input"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="可选，建议填写审批原因"
            disabled={disabled}
          />
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <input
          id="auto_resume"
          type="checkbox"
          checked={autoResume}
          onChange={(event) => setAutoResume(event.target.checked)}
          disabled={disabled}
        />
        <label htmlFor="auto_resume" className="muted">
          审批通过后自动恢复（approve 时生效）
        </label>
      </div>

      <div className="toolbar">
        <button
          type="button"
          className="button"
          disabled={!canApprove || disabled}
          onClick={handleApprove}
        >
          {loadingAction === "approve" ? "提交中..." : "通过并恢复"}
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={!canReject || disabled}
          onClick={handleReject}
        >
          {loadingAction === "reject" ? "提交中..." : "拒绝审批"}
        </button>
        <button
          type="button"
          className="button secondary"
          disabled={!canResume || disabled}
          onClick={handleResume}
        >
          {loadingAction === "resume" ? "提交中..." : "手动恢复"}
        </button>
      </div>

      {resultMessage ? <div className="card">{resultMessage}</div> : null}
      {errorMessage ? <div className="card">操作失败：{errorMessage}</div> : null}
    </div>
  );
}
