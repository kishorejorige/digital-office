export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  let classes = "bg-surface2 text-textSecondary border border-border"
  if (normalized === "pending") classes = "bg-warning/10 text-warning border border-warning/40"
  if (normalized === "approved") classes = "bg-success/10 text-success border border-success/40"
  if (normalized === "rejected") classes = "bg-danger/10 text-danger border border-danger/40"
  if (normalized === "new") classes = "bg-accent/10 text-accent border border-accent/40"
  if (normalized === "maybe" || normalized === "skip" || normalized === "apply") classes = "bg-surface2 text-textSecondary border border-border"
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs tracking-wide uppercase ${classes}`}>
      {status}
    </span>
  )
}

