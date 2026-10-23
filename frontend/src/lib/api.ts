import type { Approval, Lead, TaskRequest, TaskResponse } from "../types"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8585"

export async function fetchHealth() {
  const res = await fetch(`${API_BASE_URL}/`)
  if (!res.ok) {
    throw new Error("Failed to fetch health")
  }
  return res.json()
}

export async function fetchLeads(): Promise<Lead[]> {
  const res = await fetch(`${API_BASE_URL}/leads`)
  if (!res.ok) {
    throw new Error("Failed to fetch leads")
  }
  return res.json()
}

export async function fetchApprovals(): Promise<Approval[]> {
  const res = await fetch(`${API_BASE_URL}/approvals`)
  if (!res.ok) {
    throw new Error("Failed to fetch approvals")
  }
  return res.json()
}

export async function createProposal(leadId: number): Promise<Approval> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/leads/${leadId}/proposal`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
  } catch (err) {
    throw new Error("Network error while creating proposal draft")
  }

  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Lead not found")
    }
    if (res.status === 409) {
      let message = "Approval state conflict"
      try {
        const data = await res.json()
        if (data && typeof data.detail === "string") {
          message = data.detail
        }
      } catch {
        // ignore
      }
      throw new Error(message)
    }
    if (res.status === 422) {
      throw new Error("Invalid request")
    }
    let message = "Failed to create proposal draft"
    try {
      const data = await res.json()
      if (data && typeof data.detail === "string") {
        message = data.detail
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  try {
    return (await res.json()) as Approval
  } catch {
    throw new Error("Unexpected response from server")
  }
}

export async function approveProposal(approvalId: number): Promise<Approval> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/approvals/${approvalId}/approve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
  } catch (err) {
    throw new Error("Network error while approving proposal")
  }

  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Approval not found")
    }
    if (res.status === 409) {
      let message = "This approval may already have been approved or rejected. Refreshing the list."
      try {
        const data = await res.json()
        if (data && typeof data.detail === "string") {
          message = data.detail
        }
      } catch {
        // ignore
      }
      throw new Error(message)
    }
    if (res.status === 500) {
      throw new Error("Unable to update approval due to a database error")
    }
    let message = "Failed to approve proposal"
    try {
      const data = await res.json()
      if (data && typeof data.detail === "string") {
        message = data.detail
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  try {
    return (await res.json()) as Approval
  } catch {
    throw new Error("Unexpected response from server")
  }
}

export async function rejectProposal(approvalId: number): Promise<Approval> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/approvals/${approvalId}/reject`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    })
  } catch (err) {
    throw new Error("Network error while rejecting proposal")
  }

  if (!res.ok) {
    if (res.status === 404) {
      throw new Error("Approval not found")
    }
    if (res.status === 409) {
      let message = "This approval may already have been approved or rejected. Refreshing the list."
      try {
        const data = await res.json()
        if (data && typeof data.detail === "string") {
          message = data.detail
        }
      } catch {
        // ignore
      }
      throw new Error(message)
    }
    if (res.status === 500) {
      throw new Error("Unable to update approval due to a database error")
    }
    let message = "Failed to reject proposal"
    try {
      const data = await res.json()
      if (data && typeof data.detail === "string") {
        message = data.detail
      }
    } catch {
      // ignore
    }
    throw new Error(message)
  }

  try {
    return (await res.json()) as Approval
  } catch {
    throw new Error("Unexpected response from server")
  }
}

export async function submitTask(task: string): Promise<TaskResponse> {
  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}/tasks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ task } satisfies TaskRequest),
    })
  } catch (err) {
    throw new Error("Network error while submitting task")
  }

  if (!res.ok) {
    if (res.status === 422) {
      throw new Error("Invalid task. Please provide a non-blank task (max 2000 characters).")
    }
    let message = "Failed to submit task"
    try {
      const data = await res.json()
      if (data && typeof data.detail === "string") {
        message = data.detail
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }

  try {
    return (await res.json()) as TaskResponse
  } catch {
    throw new Error("Unexpected response from server")
  }
}

export { API_BASE_URL }


