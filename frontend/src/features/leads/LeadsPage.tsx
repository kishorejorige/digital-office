import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import { Users, Search, AlertCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/Card"
import { EmptyState } from "../../components/EmptyState"
import { StatusBadge } from "../../components/StatusBadge"
import { createProposal, fetchLeads } from "../../lib/api"
import type { Lead } from "../../types"

type SortKey = "id_desc" | "fit_desc" | "payment_desc" | "title_asc"

export default function LeadsPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["leads"],
    queryFn: fetchLeads,
  })

  const [search, setSearch] = useState("")
  const [decisionFilter, setDecisionFilter] = useState("all")
  const [statusFilter, setStatusFilter] = useState("all")
  const [sortKey, setSortKey] = useState<SortKey>("id_desc")
  const [expanded, setExpanded] = useState<Record<number, boolean>>({})
  const [creatingFor, setCreatingFor] = useState<number | null>(null)
  const [proposalMessage, setProposalMessage] = useState<string | null>(null)
  const [proposalError, setProposalError] = useState<string | null>(null)

  const leads = Array.isArray(data) ? data : []

  const decisionOptions = useMemo(() => {
    const set = new Set<string>()
    for (const lead of leads) {
      if (lead.decision) set.add(lead.decision)
    }
    return Array.from(set).sort()
  }, [leads])

  const statusOptions = useMemo(() => {
    const set = new Set<string>()
    for (const lead of leads) {
      if (lead.status) set.add(lead.status)
    }
    return Array.from(set).sort()
  }, [leads])

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase()
    let items = leads.slice()
    if (term) {
      items = items.filter((lead) => {
        const haystack = [
          lead.title,
          lead.source,
          lead.description || "",
          lead.budget || "",
          lead.url || "",
          lead.name || "",
        ]
          .join(" ")
          .toLowerCase()
        return haystack.includes(term)
      })
    }
    if (decisionFilter !== "all") {
      items = items.filter((lead) => lead.decision === decisionFilter)
    }
    if (statusFilter !== "all") {
      items = items.filter((lead) => lead.status === statusFilter)
    }
    items.sort((a, b) => {
      if (sortKey === "id_desc") return b.id - a.id
      if (sortKey === "fit_desc") return (b.fit_score || 0) - (a.fit_score || 0)
      if (sortKey === "payment_desc") return (b.payment_score || 0) - (a.payment_score || 0)
      if (sortKey === "title_asc") return a.title.localeCompare(b.title)
      return b.id - a.id
    })
    return items
  }, [leads, search, decisionFilter, statusFilter, sortKey])

  const toggleExpanded = (id: number) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const handleCreateProposal = async (lead: Lead) => {
    setProposalMessage(null)
    setProposalError(null)
    setCreatingFor(lead.id)
    try {
      const approval = await createProposal(lead.id)
      setProposalMessage(`Proposal draft created (Approval #${approval.id}) for "${lead.title}". It is pending approval.`)
    } catch (err) {
      if (err instanceof Error) {
        setProposalError(err.message)
      } else {
        setProposalError("Failed to create proposal draft")
      }
    } finally {
      setCreatingFor(null)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Leads</h1>
        <p className="text-sm text-textSecondary mt-1">Lead pipeline and proposal drafting</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters & Search</CardTitle>
          <CardDescription>Search and filter leads (client-side)</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-textSecondary" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search title, source, description..."
                className="w-full rounded-lg border border-border bg-surface2/40 pl-8 pr-3 py-2 text-sm text-textPrimary placeholder:text-textSecondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                aria-label="Search leads"
              />
            </div>
            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              className="rounded-lg border border-border bg-surface2/40 px-3 py-2 text-sm text-textPrimary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Filter by decision"
            >
              <option value="all">All decisions</option>
              {decisionOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-surface2/40 px-3 py-2 text-sm text-textPrimary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Filter by status"
            >
              <option value="all">All statuses</option>
              {statusOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="rounded-lg border border-border bg-surface2/40 px-3 py-2 text-sm text-textPrimary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              aria-label="Sort leads"
            >
              <option value="id_desc">Newest first</option>
              <option value="fit_desc">Fit score (high to low)</option>
              <option value="payment_desc">Payment score (high to low)</option>
              <option value="title_asc">Title (A-Z)</option>
            </select>
          </div>
          {(proposalMessage || proposalError) && (
            <div className="mt-4 space-y-2">
              {proposalMessage && (
                <div className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm text-success flex flex-col gap-1">
                  <span>{proposalMessage}</span>
                  <Link to="/proposals" className="text-accent hover:underline">
                    View Proposals & Approvals
                  </Link>
                </div>
              )}
              {proposalError && (
                <div className="flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                  <AlertCircle className="h-4 w-4 mt-0.5" />
                  <span>{proposalError}</span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Leads ({filtered.length})</CardTitle>
          <CardDescription>From GET /leads</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading && (
            <div className="flex items-center gap-2 px-5 py-4 text-sm text-textSecondary">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading leads...
            </div>
          )}
          {isError && (
            <div className="px-5 py-4 space-y-2">
              <div className="flex items-start gap-2 text-sm text-danger">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <span>Failed to load leads</span>
              </div>
              <button
                onClick={() => refetch()}
                className="inline-flex items-center rounded-lg border border-border px-3 py-1.5 text-sm text-textPrimary hover:bg-surface2/60"
              >
                Retry
              </button>
            </div>
          )}
          {!isLoading && !isError && leads.length === 0 && (
            <EmptyState icon={Users} title="No leads yet" description="Leads appear when created or saved by the research agent." />
          )}
          {!isLoading && !isError && leads.length > 0 && filtered.length === 0 && (
            <EmptyState icon={Search} title="No matches" description="Adjust search or filters to see leads." />
          )}
          {!isLoading && !isError && filtered.length > 0 && (
            <div className="divide-y divide-border">
              {filtered.map((lead) => {
                const isExpanded = expanded[lead.id]
                const isCreating = creatingFor === lead.id
                return (
                  <div key={lead.id} className="px-5 py-4 space-y-3">
                    <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                      <div className="space-y-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-textPrimary truncate">{lead.title}</p>
                          <StatusBadge status={lead.status || "new"} />
                          <StatusBadge status={lead.decision} />
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-textSecondary">
                          <span>Source: {lead.source}</span>
                          {lead.budget && <span>Budget: {lead.budget}</span>}
                          <span>ID: {lead.id}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-textSecondary">
                          <span>Fit: {lead.fit_score}</span>
                          <span>Payment: {lead.payment_score}</span>
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => handleCreateProposal(lead)}
                          disabled={isCreating}
                          className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-background transition-colors hover:bg-accentHover disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                        >
                          {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
                          {isCreating ? "Creating..." : "Create proposal draft"}
                        </button>
                        <button
                          onClick={() => toggleExpanded(lead.id)}
                          className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm text-textPrimary hover:bg-surface2/60"
                          aria-expanded={isExpanded}
                        >
                          {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          Details
                        </button>
                      </div>
                    </div>
                    {isExpanded && (
                      <div className="rounded-lg border border-borderSubtle bg-surface2/30 p-3 space-y-2 text-sm">
                        {lead.description && (
                          <div>
                            <p className="text-xs text-textSecondary">Description</p>
                            <p className="text-textPrimary whitespace-pre-wrap">{lead.description}</p>
                          </div>
                        )}
                        {lead.url && (
                          <div>
                            <p className="text-xs text-textSecondary">URL</p>
                            <a href={lead.url} target="_blank" rel="noreferrer" className="text-accent hover:underline break-all">
                              {lead.url}
                            </a>
                          </div>
                        )}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-textSecondary">
                          <div className="rounded-lg border border-borderSubtle px-2 py-1">
                            Contacted: <span className="text-textPrimary">{lead.contacted ? "Yes" : "No"}</span>
                          </div>
                          <div className="rounded-lg border border-borderSubtle px-2 py-1">
                            Replied: <span className="text-textPrimary">{lead.replied ? "Yes" : "No"}</span>
                          </div>
                          <div className="rounded-lg border border-borderSubtle px-2 py-1">
                            Earned: <span className="text-textPrimary">{lead.earned_amount}</span>
                          </div>
                          {lead.name && (
                            <div className="rounded-lg border border-borderSubtle px-2 py-1">
                              Name: <span className="text-textPrimary">{lead.name}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
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

