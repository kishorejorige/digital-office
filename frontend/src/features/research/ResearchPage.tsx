import { FormEvent, useState } from "react"
import { Search, AlertCircle, Loader2 } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/Card"
import { EmptyState } from "../../components/EmptyState"
import { StatusBadge } from "../../components/StatusBadge"
import { submitTask } from "../../lib/api"
import type { ResearchTaskResponse, TaskAcceptedResponse, TaskResponse } from "../../types"

function isResearchResponse(res: TaskResponse): res is ResearchTaskResponse {
  return "agent" in res && res.agent === "research"
}

export default function ResearchPage() {
  const [task, setTask] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TaskResponse | null>(null)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const trimmed = task.trim()
    if (trimmed.length === 0) {
      setError("Please enter a task.")
      return
    }
    if (trimmed.length > 2000) {
      setError("Task must be 2000 characters or less.")
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await submitTask(trimmed)
      setResult(response)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError("Unexpected error while submitting task")
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Research & Tasks</h1>
        <p className="text-sm text-textSecondary mt-1">Task routing and research agent</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Submit a task</CardTitle>
          <CardDescription>Tasks are routed by keywords. Research tasks use sample opportunities.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="task" className="text-sm font-medium text-textPrimary">
                Task description
              </label>
              <textarea
                id="task"
                value={task}
                onChange={(e) => setTask(e.target.value)}
                rows={4}
                maxLength={2005}
                placeholder="e.g., Find freelance Python automation opportunities"
                className="w-full rounded-lg border border-border bg-surface2/40 px-3 py-2 text-sm text-textPrimary placeholder:text-textSecondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              />
              <div className="flex items-center justify-between text-xs text-textSecondary">
                <span>Trimmed, non-blank, max 2000 characters</span>
                <span>{task.trim().length}/2000</span>
              </div>
            </div>
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
                <AlertCircle className="h-4 w-4 mt-0.5" />
                <span>{error}</span>
              </div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-accentHover disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? "Submitting..." : "Submit task"}
            </button>
          </form>
          <p className="mt-4 text-xs text-textSecondary">
            Note: The current research agent uses sample opportunities and does not perform live internet research. Only &quot;research&quot;-routed tasks run the agent; proposals/emails/calendar are not implemented yet.
          </p>
        </CardContent>
      </Card>

      {result && isResearchResponse(result) && (
        <Card>
          <CardHeader>
            <CardTitle>Research results</CardTitle>
            <CardDescription>
              Agent: {result.agent} · Count: {result.count} · Saved leads: {result.saved_leads}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {result.opportunities.length === 0 && (
              <EmptyState icon={Search} title="No opportunities" description="The sample set returned no opportunities." />
            )}
            {result.opportunities.length > 0 && (
              <div className="divide-y divide-border">
                {result.opportunities.map((opportunity, index) => (
                  <div key={`${opportunity.title}-${index}`} className="py-4 first:pt-0 last:pb-0">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-textPrimary">{opportunity.title}</p>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-textSecondary">
                          {opportunity.budget && <span>Budget: {opportunity.budget}</span>}
                          {opportunity.url && (
                            <a href={opportunity.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                              Link
                            </a>
                          )}
                        </div>
                        {Array.isArray(opportunity.skills) && opportunity.skills.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {opportunity.skills.map((skill) => (
                              <span key={skill} className="rounded-full border border-border px-2 py-0.5 text-xs text-textSecondary">
                                {skill}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={opportunity.decision} />
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-textSecondary">
                      <div className="rounded-lg border border-borderSubtle bg-surface2/40 px-2 py-1">
                        Fit score: <span className="text-textPrimary">{opportunity.fit_score}</span>
                      </div>
                      <div className="rounded-lg border border-borderSubtle bg-surface2/40 px-2 py-1">
                        Payment score: <span className="text-textPrimary">{opportunity.payment_score}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {result && !isResearchResponse(result) && ("route" in result) && (
        <Card>
          <CardHeader>
            <CardTitle>Task accepted</CardTitle>
            <CardDescription>Route: {(result as TaskAcceptedResponse).route}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-textPrimary">Your task was accepted and routed to <span className="font-medium">{(result as TaskAcceptedResponse).route}</span>.</p>
            <p className="text-sm text-textSecondary">
              This route is not yet implemented in the current backend. No agent processed this task, and no records were created by this action. Proposals, emails, and calendar actions remain disabled for safety.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}

