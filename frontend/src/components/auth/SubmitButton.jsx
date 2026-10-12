// SubmitButton — 主提交按钮（对标参考 .btn-filled，busy 态切换文案）

export default function SubmitButton({ label, busyLabel, busy = false, disabled = false }) {
  return (
    <button className="btn-filled" type="submit" disabled={busy || disabled}>
      {busy ? busyLabel : label}
    </button>
  )
}
