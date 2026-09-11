import api, { parseSSE } from './client'
import type { AgentResult, AgentRunRequest, AgentStreamEvent, PlanStep, ToolInfo } from '../types'

/**
 * Run the agent synchronously.
 */
export async function runAgent(
  query: string,
  options?: { maxSteps?: number; planFirst?: boolean },
): Promise<AgentResult> {
  const request: AgentRunRequest = {
    query,
    max_steps: options?.maxSteps ?? 5,
    plan_first: options?.planFirst ?? true,
  }
  const response = await api.post<AgentResult>('/agent/run', request)
  return response.data
}

/**
 * Run the agent with SSE streaming.
 */
export async function streamAgent(
  query: string,
  onEvent: (event: AgentStreamEvent) => void,
  options?: { maxSteps?: number; planFirst?: boolean },
): Promise<void> {
  const response = await fetch('/api/v1/agent/run-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      max_steps: options?.maxSteps ?? 5,
      plan_first: options?.planFirst ?? true,
      stream: true,
    }),
  })

  if (!response.ok) {
    throw new Error(`Agent request failed: ${response.status}`)
  }

  await parseSSE(response, (event) => onEvent(event as unknown as AgentStreamEvent))
}

/**
 * Generate a plan without executing.
 */
export async function generatePlan(query: string): Promise<{ query: string; steps: PlanStep[] }> {
  const response = await api.post('/agent/plan', { query })
  return response.data
}

/**
 * List all available tools.
 */
export async function listTools(): Promise<{ tools: ToolInfo[]; total: number }> {
  const response = await api.get('/agent/tools')
  return response.data
}
