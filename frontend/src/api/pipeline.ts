import api, { parseSSE } from './client'
import type { PipelineResult, PipelineRunRequest } from '../types'

/**
 * Run the pipeline synchronously.
 */
export async function runPipeline(query: string): Promise<PipelineResult> {
  const request: PipelineRunRequest = { query }
  const response = await api.post<PipelineResult>('/pipeline/run', request)
  return response.data
}

/**
 * Run the pipeline with SSE streaming.
 * Calls onEvent for each SSE event.
 */
export async function streamPipeline(
  query: string,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  const response = await fetch('/api/v1/pipeline/run-stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, stream: true }),
  })

  if (!response.ok) {
    throw new Error(`Pipeline request failed: ${response.status}`)
  }

  await parseSSE(response, onEvent)
}

/**
 * Get list of pipeline stages.
 */
export async function getStages(): Promise<{ stages: { name: string; index: number }[] }> {
  const response = await api.get('/pipeline/stages')
  return response.data
}
