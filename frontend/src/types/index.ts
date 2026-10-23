export interface HealthResponse {
  app: string
  status: string
  version: string
}

export interface Lead {
  id: number
  name?: string | null
  source: string
  title: string
  description?: string | null
  url?: string | null
  budget?: string | null
  fit_score: number
  payment_score: number
  decision: string
  status: string
  contacted: boolean
  replied: boolean
  earned_amount: number
}

export interface Approval {
  id: number
  lead_id: number
  approval_type: string
  draft: string
  status: string
}

export interface TaskRequest {
  task: string
}

export interface ResearchOpportunity {
  title: string
  skills?: string[]
  budget?: string
  url?: string
  fit_score: number
  payment_score: number
  decision: "APPLY" | "MAYBE" | "SKIP" | string
}

export interface ResearchTaskResponse {
  agent: "research"
  task: string
  status: "completed"
  count: number
  saved_leads: number
  opportunities: ResearchOpportunity[]
}

export interface TaskAcceptedResponse {
  task: string
  route: "email" | "calendar" | "unknown"
  status: "accepted"
}

export type TaskResponse = ResearchTaskResponse | TaskAcceptedResponse

