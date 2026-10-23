import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { AlertCircle, CheckCircle2, FileText, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/Card"
import { EmptyState } from "../../components/EmptyState"
import { StatusBadge } from "../../components/StatusBadge"
import { approveProposal, fetchApprovals, fetchLeads, rejectProposal } from "../../lib/api"
import type { Approval, Lead } from "../../types"

export default function ProposalsPage() {
  const approvalsQuery = useQuery({
    queryKey: ["approvals"],
    queryFn: fetchApprovals,
  })
  const leadsQuery = useQuery({
    queryKey: ["leads"],
    queryFn: fetchLeads,
  })

  const approvals = Array.isArray(approvalsQuery.data) ? approvalsQuery.data : []
  const leads = Array.isArray(leadsQuery.data) ? leadsQuery.data : []

  const leadMap = useMemo(() => {
    const map = new Map<number, Lead>()
    for (const lead of leads) {
      map.set(lead.id, lead)
    }
    return map
  }, [leads])

  const [processing, setProcessing] = useState<Record<number, "approve" | "reject">>({})
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null)
  const [confirm, setConfirm] = useState<{ approval: Approval; action: "approve" | "reject" } | null>(null)

  const isLoading = approvalsQuery.isLoading || leadsQuery.isLoading
  const isError = approvalsQuery.isError || leadsQuery.isError

  const handleRefresh = () => {
    setFeedback(null)
    approvalsQuery.refetch()
    leadsQuery.refetch()
  }

  const requestAction = (approval: Approval, action: "approve" | "reject") => {
    setFeedback(null)
    setConfirm({ approval, action })
  }

  const confirmAction = async () => {
    if (!confirm) return
    const { approval, action } = confirm
    setConfirm(null)
    setFeedback(null)
    setProcessing((prev) => ({ ...prev, [approval.id]: action }))
    try {
      if (action === "approve") {
        await approveProposal(approval.id)
        setFeedback({ type: "success", message: `Approved proposal (Approval #${approval.id}).` })
      } else {
        await rejectProposal(approval.id)
        setFeedback({ type: "success", message: `Rejected proposal (Approval #${approval.id}).` })
      }
      approvalsQuery.refetch()
    } catch (err) {
      if (err instanceof Error) {
        setFeedback({ type: "error", message: err.message })
        if (err.message.toLowerCase().includes("already")) {
          approvalsQuery.refetch()
        }
      } else {
        setFeedback({ type: "error", message: "Failed to update approval" })
      }
    } finally {
      setProcessing((prev) => {
        const next = { ...prev }
        delete next[approval.id]
        return next
      })
    }
  }

  const cancelConfirm = () => {
    setConfirm(null)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Proposals & Approvals</h1>
        <p className="text-sm text-textSecondary mt-1">Approval queue</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex items-start gap-2 rounded-lg border border-borderSubtle bg-surface2/40 px-3 py-2 text-sm text-textSecondary">
            <AlertCircle className="h-4 w-4 mt-0.5 text-textSecondary" />
            <span>Approving or rejecting a proposal records your decision only. It does not send an email.</span>
          </div>
        </CardContent>
      </Card>

      {(feedback || confirm) && (
        <Card>
          <CardContent className="pt-6 space-y-3">
            {feedback && feedback.type === "success" && (
              <div className="flex items-start gap-2 rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                <CheckCircle2 className="h-4 w-4 mt-0.5" />
                <span>{feedback.message}</span>
              </div>
            )}
            {feedback && feedback.type === "error" && (
              <div className="flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <span>{feedback.message}</span>
              </div>
            )}
            {confirm && (
              <div className="rounded-lg border border-border bg-surface2/40 p-3 space-y-3">
                <div>
                  <p className="text-sm font-medium text-textPrimary">
                    {confirm.action === "approve" ? "Approve proposal?" : "Reject proposal?"}
                  </p>
                  <p className="text-sm text-textSecondary mt-1">
                    {confirm.action === "approve"
                      ? "This will mark the proposal as approved. This action cannot be undone from this page."
                      : "This will mark the proposal as rejected. This action cannot be undone from this page."}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={confirmAction}
                    className="inline-flex items-center rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-background hover:bg-accentHover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    Confirm {confirm.action === "approve" ? "Approve" : "Reject"}
                  </button>
                  <button
                    onClick={cancelConfirm}
                    className="inline-flex items-center rounded-lg border border-border px-3 py-1.5 text-sm text-textPrimary hover:bg-surface2/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Pending approvals ({approvals.length})</CardTitle>
          <CardDescription>From GET /approvals (pending only)</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <div className="flex items-center gap-2 px-5 py-4 text-sm text-textSecondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading approvals...
            </div>
          )}
          {isError && (
            <div className="px-5 py-4 space-y-2">
              <div className="flex items-start gap-2 text-sm text-danger">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <span>Failed to load approvals or leads</span>
              </div>
              <button
                onClick={handleRefresh}
                className="inline-flex items-center rounded-lg border border-border px-3 py-1.5 text-sm text-textPrimary hover:bg-surface2/60"
              >
                Retry
              </button>
            </div>
          )}
          {!isLoading && !isError && approvals.length === 0 && (
            <EmptyState icon={FileText} title="No pending proposals" description="All proposals have been reviewed or none exist yet." />
          )}
          {!isLoading && !isError && approvals.length > 0 && (
            <div className="divide-y divide-border">
              {approvals.map((approval) => {
                const lead = leadMap.get(approval.lead_id)
                const isProcessing = processing[approval.id]
                return (
                  <div key={approval.id} className="px-5 py-4 space-y-4">
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                      <div className="space-y-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-textPrimary">Approval #{approval.id}</p>
                          <StatusBadge status={approval.status || "pending"} />
                          <StatusBadge status={approval.approval_type} />
                        </div>
                        <p className="text-sm text-textPrimary">{lead?.title || `Lead #${approval.lead_id}`}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-textSecondary">
                          {lead?.source && <span>Source: {lead.source}</span>}
                          {lead?.budget && <span>Budget: {lead.budget}</span>}
                          {lead && <span>Fit: {lead.fit_score}</span>}
                          {lead && <span>Payment: {lead.payment_score}</span>}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => requestAction(approval, "approve")}
                          disabled={!!isProcessing}
                          className="inline-flex items-center gap-2 rounded-lg bg-success px-3 py-1.5 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success"
                        >
                          {isProcessing === "approve" && <Loader2 className="h-4 w-4 animate-spin" />}
                          {isProcessing === "approve" ? "Approving..." : "Approve"}
                        </button>
                        <button
                          onClick={() => requestAction(approval, "reject")}
                          disabled={!!isProcessing}
                          className="inline-flex items-center gap-2 rounded-lg bg-danger px-3 py-1.5 text-sm font-medium text-background transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger"
                        >
                          {isProcessing === "reject" && <Loader2 className="h-4 w-4 animate-spin" />}
                          {isProcessing === "reject" ? "Rejecting..." : "Reject"}
                        </button>
                      </div>
                    </div>
                    {lead && (lead.description || lead.url) && (
                      <div className="rounded-lg border border-borderSubtle bg-surface2/30 p-3 space-y-2 text-sm">
                        {lead.description && (
                          <div>
                            <p className="text-xs text-textSecondary">Lead description</p>
                            <p className="text-textPrimary whitespace-pre-wrap">{lead.description}</p>
                          </div>
                        )}
                        {lead.url && (
                          <div>
                            <p className="text-xs text-textSecondary">Lead URL</p>
                            <a href={lead.url} target="_blank" rel="noreferrer" className="text-accent hover:underline break-all">
                              {lead.url}
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                    <div className="rounded-lg border border-border bg-surface/60 p-3 space-y-2">
                      <p className="text-xs text-textSecondary">Proposal draft</p>
                      <pre className="text-sm text-textPrimary whitespace-pre-wrap font-sans leading-relaxed">{approval.draft}</pre>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

