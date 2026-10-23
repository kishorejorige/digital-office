import { useQuery } from "@tanstack/react-query"
import { fetchApprovals, fetchLeads } from "../../lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/Card"
import { StatusBadge } from "../../components/StatusBadge"
import { EmptyState } from "../../components/EmptyState"
import { Users, Search, Inbox } from "lucide-react"

export default function OverviewPage() {
  const { data: leads, isLoading: leadsLoading } = useQuery({ queryKey: ["leads"], queryFn: fetchLeads })
  const { data: approvals, isLoading: approvalsLoading } = useQuery({ queryKey: ["approvals"], queryFn: fetchApprovals })

  const leadCount = Array.isArray(leads) ? leads.length : 0
  const pendingCount = Array.isArray(approvals) ? approvals.length : 0

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="text-sm text-textSecondary mt-1">Operational snapshot of Digital Office</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Leads</CardTitle>
            <CardDescription>Total leads in pipeline</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold tracking-tight">{leadsLoading ? "—" : leadCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Pending Approvals</CardTitle>
            <CardDescription>Awaiting human review</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold tracking-tight">{approvalsLoading ? "—" : pendingCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Research & Tasks</CardTitle>
            <CardDescription>Submit tasks to the router</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm text-textSecondary">
              <Search className="h-4 w-4" />
              <span>Available via /tasks</span>
            </div>
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Lead Preview</CardTitle>
            <CardDescription>Recent leads from GET /leads</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {leadsLoading && <div className="px-5 py-4 text-sm text-textSecondary">Loading...</div>}
            {!leadsLoading && Array.isArray(leads) && leads.length === 0 && (
              <EmptyState icon={Users} title="No leads yet" description="Leads appear when created or saved by the research agent." />
            )}
            {!leadsLoading && Array.isArray(leads) && leads.length > 0 && (
              <div className="divide-y divide-border">
                {leads.slice(0, 5).map((lead: any) => (
                  <div key={lead.id} className="px-5 py-3 flex items-center justify-between gap-4 hover:bg-surface2/40 transition-colors">
                    <div className="min-w-0">
                      <p className="text-sm truncate text-textPrimary">{lead.title}</p>
                      <p className="text-xs text-textSecondary truncate">{lead.source}</p>
                    </div>
                    <StatusBadge status={lead.status || "new"} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Approval Preview</CardTitle>
            <CardDescription>Pending items from GET /approvals</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {approvalsLoading && <div className="px-5 py-4 text-sm text-textSecondary">Loading...</div>}
            {!approvalsLoading && Array.isArray(approvals) && approvals.length === 0 && (
              <EmptyState icon={Inbox} title="No pending approvals" description="Proposals appear here after creation." />
            )}
            {!approvalsLoading && Array.isArray(approvals) && approvals.length > 0 && (
              <div className="divide-y divide-border">
                {approvals.slice(0, 5).map((approval: any) => (
                  <div key={approval.id} className="px-5 py-3 flex items-center justify-between gap-4 hover:bg-surface2/40 transition-colors">
                    <div className="min-w-0">
                      <p className="text-sm truncate text-textPrimary">Approval #{approval.id}</p>
                      <p className="text-xs text-textSecondary truncate">Lead #{approval.lead_id} · {approval.approval_type}</p>
                    </div>
                    <StatusBadge status={approval.status} />
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

